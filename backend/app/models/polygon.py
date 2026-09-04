from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Polygon(Base):
    """Контур АОИ/поля. `id` — это `anon_polygon_id` из датасета соревнования
    для сидовых полигонов (напр. `AOI-0002`) либо `custom-<uuid>` для
    нарисованных пользователем."""

    __tablename__ = "polygons"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str | None] = mapped_column(String(255))
    crop_type: Mapped[str | None] = mapped_column(String(255))
    area_id: Mapped[str | None] = mapped_column(String(64))
    points: Mapped[list] = mapped_column(JSONB, nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    owner: Mapped["User | None"] = relationship(back_populates="polygons")
    observations: Mapped[list["NdviObservation"]] = relationship(
        back_populates="polygon", cascade="all, delete-orphan"
    )
    anomalies: Mapped[list["AnomalyPeriod"]] = relationship(
        back_populates="polygon", cascade="all, delete-orphan"
    )
