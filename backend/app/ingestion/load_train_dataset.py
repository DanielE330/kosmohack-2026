"""Разовая загрузка `data/train_dataset.csv` в БД. Отдельный CLI, не часть
веб-сервиса — веб-сервис и приём/пересчёт данных не завязаны друг на друга.

Запуск (из backend/, при поднятой БД и применённых миграциях):
    python -m app.ingestion.load_train_dataset [--csv ../data/train_dataset.csv]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.enums import NdviStatus
from app.models.polygon import Polygon
from app.models.timeseries import NdviObservation
from app.services.anomaly_detection import group_into_periods
from app.services.gapfill import fill_gaps

STATUS_MAP = {
    "Штатное развитие": NdviStatus.normal,
    "Угнетение биомассы": NdviStatus.suppression,
    "Критическая аномалия": NdviStatus.critical,
}

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "train_dataset.csv"

_SENSOR_COLUMNS = [
    "s2_ndvi",
    "s2_evi",
    "s2_ndwi",
    "landsat_ndvi",
    "landsat_evi",
    "landsat_ndwi",
    "modis_ndvi",
    "modis_evi",
    "era5_temp_c",
    "era5_precip_mm",
    "primary_ndvi",
    "ndvi_climatology_mean",
    "ndvi_climatology_std",
    "ndvi_zscore",
]


def _placeholder_points(polygon_id: str) -> list[list[float]]:
    """AOI из train_dataset.csv не содержат координат — контур синтетический,
    для отображения на карте, пока не появятся реальные координаты (см.
    tasks/backend.md, п.0). Замените на реальную геометрию (OSM/ESA
    WorldCereal), когда она будет известна."""
    digest = hashlib.sha1(polygon_id.encode()).hexdigest()
    grid_x = int(digest[:4], 16) % 40
    grid_y = int(digest[4:8], 16) % 40
    base_lat = 46.0 + grid_y * 0.05
    base_lon = 39.0 + grid_x * 0.05
    d = 0.01
    return [
        [base_lat, base_lon],
        [base_lat, base_lon + d],
        [base_lat + d, base_lon + d],
        [base_lat + d, base_lon],
    ]


def _nn(value: object) -> float | None:
    return None if value is None or pd.isna(value) else float(value)


async def _load_polygon(db: AsyncSession, polygon_id: str, group: pd.DataFrame) -> None:
    existing = await db.get(Polygon, polygon_id)
    if existing is None:
        mode = group["crop_type"].mode()
        crop_type = mode.iat[0] if not mode.empty else None
        db.add(
            Polygon(
                id=polygon_id,
                label=polygon_id,
                crop_type=crop_type,
                is_custom=False,
                points=_placeholder_points(polygon_id),
            )
        )
        await db.flush()

    observations: list[NdviObservation] = []
    for row in group.itertuples(index=False):
        r = row._asdict()
        obs = NdviObservation(
            polygon_id=polygon_id,
            date=r["date"],
            doy=int(r["doy"]) if not pd.isna(r.get("doy")) else None,
            is_synthetic_gap=False,
            n_reference_years=int(r["n_reference_years"]) if not pd.isna(r.get("n_reference_years")) else None,
            status=STATUS_MAP.get(r.get("status")),
            crop_type=r.get("crop_type"),
            **{col: _nn(r.get(col)) for col in _SENSOR_COLUMNS},
        )
        db.add(obs)
        observations.append(obs)

    fill_gaps(observations)

    # Периоды аномалий строятся из готового `status`, посчитанного
    # организаторами (формулу Z-score не пересчитываем, см. tasks/backend.md).
    for period in group_into_periods(polygon_id, observations):
        db.add(period)


async def load(csv_path: Path) -> None:
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    async with AsyncSessionLocal() as db:
        for polygon_id, group in df.groupby("anon_polygon_id"):
            await _load_polygon(db, str(polygon_id), group.sort_values("date").reset_index(drop=True))
        await db.commit()

    print(f"Готово: загружено {df['anon_polygon_id'].nunique()} полигонов, {len(df)} наблюдений")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(load(args.csv))
