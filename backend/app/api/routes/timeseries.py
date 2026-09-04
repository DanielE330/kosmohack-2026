from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.polygon import Polygon
from app.models.timeseries import NdviObservation
from app.schemas.timeseries import NdviObservationIn, NdviPointOut
from app.services import anomaly_detection, gapfill

router = APIRouter(tags=["timeseries"])


@router.get(
    "/timeseries/{anon_polygon_id}",
    response_model=list[NdviPointOut],
    summary="Временной ряд NDVI по полигону",
)
async def get_timeseries(anon_polygon_id: str, db: AsyncSession = Depends(get_db)) -> list[NdviObservation]:
    polygon = await db.get(Polygon, anon_polygon_id)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Полигон не найден")

    result = await db.execute(
        select(NdviObservation).where(NdviObservation.polygon_id == anon_polygon_id).order_by(NdviObservation.date)
    )
    return list(result.scalars().all())


@router.post(
    "/timeseries/{anon_polygon_id}/upload",
    response_model=list[NdviPointOut],
    summary="Загрузить новые наблюдения ДЗЗ по полигону",
)
async def upload_timeseries(
    anon_polygon_id: str,
    rows: list[NdviObservationIn] = Body(..., description="Построчные наблюдения ДЗЗ за новые даты"),
    db: AsyncSession = Depends(get_db),
) -> list[NdviObservation]:
    """Принимает новые строки временного ряда (формат — как в
    `train_dataset.csv`/`private_features.csv`), сохраняет их и
    пересчитывает восстановление пропусков и аномалии по всему полигону
    (см. `app/services/gapfill.py`, `app/services/anomaly_detection.py` —
    используют реальную ML-модель через `app/services/ml_bridge.py`, с
    откатом на baseline-эвристики, если ML недоступен)."""
    polygon = await db.get(Polygon, anon_polygon_id)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Полигон не найден")

    existing = await db.execute(select(NdviObservation).where(NdviObservation.polygon_id == anon_polygon_id))
    by_date = {obs.date: obs for obs in existing.scalars().all()}

    for row in rows:
        obs = by_date.get(row.date)
        if obs is None:
            obs = NdviObservation(polygon_id=anon_polygon_id, date=row.date)
            db.add(obs)
            by_date[row.date] = obs
        for field, value in row.model_dump(exclude={"date"}).items():
            setattr(obs, field, value)
        obs.doy = row.date.timetuple().tm_yday

    await db.flush()
    all_observations = sorted(by_date.values(), key=lambda o: o.date)
    gapfill.fill_gaps(all_observations)
    await anomaly_detection.rebuild_anomalies(db, anon_polygon_id, all_observations)
    await db.commit()
    for obs in all_observations:
        await db.refresh(obs)
    return all_observations
