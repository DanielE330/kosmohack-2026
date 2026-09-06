"""Демо-аккаунты для показа продукта.

Раньше демо-пользователь (`demo@skytime.dev`) заводился руками — через
`POST /auth/register` + `/auth/confirm-email` на уже поднятом сервисе. Это
живёт ровно до первого пересоздания тома с базой: после `docker compose
down -v` в приложение нечем войти, а на экране входа при этом по-прежнему
написано «Демо-доступ». Поэтому аккаунты заводятся здесь — идемпотентным
сидом на старте приложения (`app.main.lifespan`).

Идемпотентность важнее полноты: повторный запуск ничего не пересоздаёт и
не перетирает — существующему аккаунту сид только чинит подтверждение
почты (без него `/auth/login` отдаёт 403 и демо не пускает внутрь).
Пароль существующего пользователя сид НЕ трогает: его могли осознанно
сменить через `/auth/change-password`, и откатывать это молча нельзя.

Роли: аккаунты отличаются не только почтой, а правами на одной общей
карте — так на демо видно, что даёт `MapMember` (см. app/models/map.py):
агроном может рисовать и править участки, аналитик и наблюдатель ту же
карту только смотрят.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.map import Map, MapMember, MapRole
from app.models.user import User
from app.security import hash_password

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DemoAccount:
    email: str
    password: str
    full_name: str
    # `None` — владелец общей демо-карты (у владельца прав editor и так
    # хватает, отдельная запись `MapMember` ему не нужна и не заводится).
    map_role: MapRole | None


# Первый в списке — владелец общей демо-карты, остальные приглашаются на
# неё с указанной ролью. Пароли намеренно простые и в одном стиле: это
# витринные аккаунты, а не боевые (продублированы на экране входа —
# `frontend/lib/data/demo_accounts.dart`, менять только синхронно).
DEMO_ACCOUNTS: tuple[DemoAccount, ...] = (
    DemoAccount("demo@skytime.dev", "demo1234", "Демо-пользователь", None),
    DemoAccount("agronom@skytime.dev", "agronom1234", "Агроном (демо)", MapRole.editor),
    DemoAccount("analyst@skytime.dev", "analyst1234", "Аналитик (демо)", MapRole.viewer),
    DemoAccount("viewer@skytime.dev", "viewer1234", "Наблюдатель (демо)", MapRole.viewer),
)


async def _get_or_create_user(db: AsyncSession, account: DemoAccount) -> User:
    result = await db.execute(select(User).where(User.email == account.email))
    user = result.scalar_one_or_none()
    if user is not None:
        if not user.is_email_confirmed:
            user.is_email_confirmed = True
            user.email_confirmation_token = None
        return user

    # Почта считается подтверждённой сразу: письмо демо-аккаунту слать
    # некуда, а без подтверждения вход запрещён (см. /auth/login).
    user = User(
        email=account.email,
        hashed_password=hash_password(account.password),
        full_name=account.full_name,
        is_email_confirmed=True,
    )
    db.add(user)
    await db.flush()
    logger.info("Заведён демо-аккаунт %s", account.email)
    return user


async def _shared_demo_map(db: AsyncSession, owner: User) -> Map:
    """Карта, которую видят все демо-аккаунты.

    Если у владельца карты уже есть — берём самую первую, а не заводим
    рядом ещё одну: на существующей уже нарисованы участки, а приглашённые
    на пустую увидели бы ноль полигонов и решили, что доступ не работает.
    Пустую карту создаём только на чистой базе, где брать всё равно
    нечего."""
    result = await db.execute(select(Map).where(Map.owner_id == owner.id).order_by(Map.id).limit(1))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    new_map = Map(name="Демо-карта SkyTime", owner_id=owner.id)
    db.add(new_map)
    await db.flush()
    return new_map


async def seed_demo_users(db: AsyncSession) -> None:
    users = {account.email: await _get_or_create_user(db, account) for account in DEMO_ACCOUNTS}

    owner_account = DEMO_ACCOUNTS[0]
    shared_map = await _shared_demo_map(db, users[owner_account.email])

    for account in DEMO_ACCOUNTS:
        if account.map_role is None:
            continue
        user = users[account.email]
        result = await db.execute(
            select(MapMember).where(
                MapMember.map_id == shared_map.id, MapMember.user_id == user.id
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            db.add(
                MapMember(
                    map_id=shared_map.id,
                    user_id=user.id,
                    invited_email=account.email,
                    role=account.map_role,
                )
            )
        elif member.role != account.map_role:
            # Роль в сиде — источник правды: если её поменяли руками во
            # время прошлого показа, возвращаем задуманную для демо.
            member.role = account.map_role

    await db.commit()


async def seed_demo_users_safe() -> None:
    """Обёртка для старта приложения: упавший сид (например, миграции ещё
    не накатаны — `alembic upgrade head` в этом проекте запускается
    отдельной командой, см. backend/README.md) не должен валить сервис.
    API без демо-аккаунтов полезнее, чем не поднявшийся вообще."""
    try:
        async with AsyncSessionLocal() as db:
            await seed_demo_users(db)
    except Exception:  # noqa: BLE001 — старт сервиса важнее причины сбоя сида
        logger.exception("Не удалось завести демо-аккаунты — сервис стартует без них")
