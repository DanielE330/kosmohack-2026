from datetime import date as date_type

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import NdviStatus


class NdviObservation(Base):
    """Одна строка временного ряда (`anon_polygon_id` + `date`), повторяет
    схему `data/train_dataset.csv` (см. `tasks/backend.md`)."""

    __tablename__ = "ndvi_observations"
    __table_args__ = (UniqueConstraint("polygon_id", "date", name="uq_polygon_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    polygon_id: Mapped[str] = mapped_column(ForeignKey("polygons.id", ondelete="CASCADE"), index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)

    s2_ndvi: Mapped[float | None] = mapped_column(Float)
    s2_evi: Mapped[float | None] = mapped_column(Float)
    s2_ndwi: Mapped[float | None] = mapped_column(Float)
    landsat_ndvi: Mapped[float | None] = mapped_column(Float)
    landsat_evi: Mapped[float | None] = mapped_column(Float)
    landsat_ndwi: Mapped[float | None] = mapped_column(Float)
    modis_ndvi: Mapped[float | None] = mapped_column(Float)
    modis_evi: Mapped[float | None] = mapped_column(Float)
    era5_temp_c: Mapped[float | None] = mapped_column(Float)
    era5_precip_mm: Mapped[float | None] = mapped_column(Float)

    doy: Mapped[int | None] = mapped_column(Integer)
    primary_ndvi: Mapped[float | None] = mapped_column(Float)
    primary_ndvi_pred: Mapped[float | None] = mapped_column(Float)
    is_synthetic_gap: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ndvi_climatology_mean: Mapped[float | None] = mapped_column(Float)
    ndvi_climatology_std: Mapped[float | None] = mapped_column(Float)
    ndvi_zscore: Mapped[float | None] = mapped_column(Float)
    n_reference_years: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[NdviStatus | None] = mapped_column(
        SAEnum(NdviStatus, name="ndvi_status", values_callable=lambda e: [m.value for m in e])
    )
    crop_type: Mapped[str | None] = mapped_column(String(255))

    polygon: Mapped["Polygon"] = relationship(back_populates="observations")
