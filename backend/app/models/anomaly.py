from datetime import date as date_type

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import NdviStatus


class AnomalyPeriod(Base):
    """Непрерывный отрезок дат со статусом suppression/critical — то, что
    отдаёт `GET /anomalies` (не по точке, а по периоду)."""

    __tablename__ = "anomaly_periods"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    polygon_id: Mapped[str] = mapped_column(ForeignKey("polygons.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    end_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    severity: Mapped[NdviStatus] = mapped_column(
        SAEnum(NdviStatus, name="ndvi_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    min_z_score: Mapped[float] = mapped_column(Float, nullable=False)
    deviation: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    polygon: Mapped["Polygon"] = relationship(back_populates="anomalies")
