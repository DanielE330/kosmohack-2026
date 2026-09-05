"""Доступ и права на картах (`Map`/`MapMember`, см. app/models/map.py).
Владелец карты неявно имеет права `editor` без отдельной записи
`MapMember` — роль хранится только для приглашённых участников."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.map import Map, MapMember, MapRole
from app.models.user import User


async def get_role(db: AsyncSession, user: User, map_: Map) -> MapRole | None:
    """`None`, если у пользователя вообще нет доступа к карте."""
    if map_.owner_id == user.id:
        return MapRole.editor
    result = await db.execute(
        select(MapMember.role).where(MapMember.map_id == map_.id, MapMember.user_id == user.id)
    )
    return result.scalar_one_or_none()


async def can_view(db: AsyncSession, user: User, map_: Map) -> bool:
    return await get_role(db, user, map_) is not None


async def can_edit(db: AsyncSession, user: User, map_: Map) -> bool:
    return await get_role(db, user, map_) == MapRole.editor


async def list_accessible_maps(db: AsyncSession, user: User) -> list[Map]:
    """Свои + те, куда пригласили — без дублей, если вдруг и то, и другое."""
    result = await db.execute(
        select(Map)
        .outerjoin(MapMember, MapMember.map_id == Map.id)
        .where(or_(Map.owner_id == user.id, MapMember.user_id == user.id))
        .distinct()
        .order_by(Map.id)
    )
    return list(result.scalars().all())


async def get_or_create_personal_map(db: AsyncSession, user: User) -> Map:
    """Карта по умолчанию для полигонов, которые пользователь создаёт, не
    указав `map_id` явно — чтобы существующий контракт `POST /polygons/
    custom` без `map_id` продолжал работать как раньше, просто теперь
    полигон оказывается на (авто-созданной) личной карте."""
    result = await db.execute(
        select(Map).where(Map.owner_id == user.id).order_by(Map.id).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    new_map = Map(name="Личная карта", owner_id=user.id)
    db.add(new_map)
    await db.flush()
    return new_map
