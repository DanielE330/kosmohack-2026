from datetime import datetime

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Подтверждение почты: реальная отправка письма пока не подключена
    # (см. tasks/backend.md) — токен возвращается напрямую в ответе
    # /auth/register как временная замена. Логика подтверждения и защита
    # логина уже настоящие, меняется только способ доставки токена.
    is_email_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    email_confirmation_token: Mapped[str | None] = mapped_column(String(64))

    # Смена пароля требует подтверждения по почте (как и смена email) —
    # новый пароль хранится захэшированным здесь до подтверждения, а не
    # прямо в `hashed_password`, чтобы неподтверждённая смена не могла
    # случайно вступить в силу. Только одна незавершённая смена может
    # существовать одновременно — новый запрос перезаписывает предыдущий.
    pending_password_hash: Mapped[str | None] = mapped_column(String(255))
    password_change_token: Mapped[str | None] = mapped_column(String(64))

    polygons: Mapped[list["Polygon"]] = relationship(back_populates="owner")
