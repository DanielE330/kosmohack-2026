import enum
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MapRole(str, enum.Enum):
    """Права участника на карте: `viewer` — только читать, `editor` — ещё
    и рисовать/менять/удалять полигоны. Владелец (`Map.owner_id`) неявно
    имеет права editor и не нуждается в отдельной записи `MapMember`."""

    viewer = "viewer"
    editor = "editor"


class Map(Base):
    """Именованная карта — коллекция полигонов одного владельца, которой
    можно поделиться (см. `MapMember`). Каждому пользователю при первом
    создании собственного полигона заводится персональная карта
    автоматически (см. `app/services/maps.py`), если он ещё не выбрал
    существующую."""

    __tablename__ = "maps"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    owner: Mapped["User"] = relationship()
    members: Mapped[list["MapMember"]] = relationship(back_populates="map", cascade="all, delete-orphan")


class MapMember(Base):
    """Доступ конкретного пользователя к чужой карте — выдаётся только
    приглашением владельца (см. `POST /maps/{id}/invite`). Приглашать можно
    только по почте уже зарегистрированного пользователя: карта — это не
    публичная ссылка, а привязка к конкретному аккаунту, поэтому
    "пригласить ещё не существующего пользователя и подключить его после
    регистрации" сознательно не реализовано — это отдельная фича (нужна
    доставка приглашения почтой, а SMTP в проекте и так нестабилен)."""

    __tablename__ = "map_members"
    __table_args__ = (UniqueConstraint("map_id", "user_id", name="uq_map_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invited_email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[MapRole] = mapped_column(SAEnum(MapRole, name="map_role"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    map: Mapped["Map"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()
