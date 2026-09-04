from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.anomaly import AnomalyPeriod
from app.schemas.anomaly import AnomalyOut

router = APIRouter(tags=["anomalies"])


@router.get(
    "/anomalies",
    response_model=list[AnomalyOut],
    summary="Периоды аномалий вегетации",
)
async def list_anomalies(
    polygon_id: str | None = Query(
        None, description="Фильтр по anon_polygon_id; без параметра — по всем полигонам", examples=["AOI-0001"]
    ),
    db: AsyncSession = Depends(get_db),
) -> list[AnomalyPeriod]:
    stmt = select(AnomalyPeriod).order_by(AnomalyPeriod.start_date)
    if polygon_id is not None:
        stmt = stmt.where(AnomalyPeriod.polygon_id == polygon_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
