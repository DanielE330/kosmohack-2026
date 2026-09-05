from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.map import Map, MapMember
from app.models.user import User
from app.schemas.map import InviteRequest, MapCreate, MapOut, MemberOut
from app.services import maps as maps_service

router = APIRouter(prefix="/maps", tags=["maps"])


def _to_out(map_: Map, role: str) -> MapOut:
    return MapOut(id=map_.id, name=map_.name, owner_id=map_.owner_id, created_at=map_.created_at, role=role)


@router.get("", response_model=list[MapOut], summary="Свои карты + те, куда пригласили")
async def list_maps(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[MapOut]:
    accessible = await maps_service.list_accessible_maps(db, current_user)
    out = []
    for m in accessible:
        role = "owner" if m.owner_id == current_user.id else (await maps_service.get_role(db, current_user, m)).value
        out.append(_to_out(m, role))
    return out


@router.post("", response_model=MapOut, status_code=status.HTTP_201_CREATED, summary="Создать новую карту")
async def create_map(
    payload: MapCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MapOut:
    new_map = Map(name=payload.name, owner_id=current_user.id)
    db.add(new_map)
    await db.commit()
    await db.refresh(new_map)
    return _to_out(new_map, "owner")


@router.get("/{map_id}/members", response_model=list[MemberOut], summary="Участники карты (кроме владельца)")
async def list_members(
    map_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberOut]:
    map_ = await db.get(Map, map_id)
    if map_ is None or not await maps_service.can_view(db, current_user, map_):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Карта не найдена")
    result = await db.execute(select(MapMember).where(MapMember.map_id == map_id))
    return list(result.scalars().all())


@router.post(
    "/{map_id}/invite",
    response_model=MemberOut,
    summary="Пригласить пользователя на карту по email (владелец карты)",
)
async def invite(
    map_id: int,
    payload: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberOut:
    map_ = await db.get(Map, map_id)
    if map_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Карта не найдена")
    if map_.owner_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Приглашать может только владелец карты")

    result = await db.execute(select(User).where(User.email == payload.email))
    invited_user = result.scalar_one_or_none()
    if invited_user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Пользователь с такой почтой не найден — приглашение доступно только для уже "
            "зарегистрированных аккаунтов",
        )
    if invited_user.id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя пригласить самого себя")

    existing = await db.execute(
        select(MapMember).where(MapMember.map_id == map_id, MapMember.user_id == invited_user.id)
    )
    member = existing.scalar_one_or_none()
    if member is not None:
        member.role = payload.role
        member.invited_email = payload.email
    else:
        member = MapMember(
            map_id=map_id, user_id=invited_user.id, invited_email=payload.email, role=payload.role
        )
        db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.delete(
    "/{map_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Убрать участника с карты (владелец карты)",
)
async def remove_member(
    map_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    map_ = await db.get(Map, map_id)
    if map_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Карта не найдена")
    if map_.owner_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Убирать участников может только владелец карты")

    result = await db.execute(
        select(MapMember).where(MapMember.map_id == map_id, MapMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Такого участника нет на этой карте")
    await db.delete(member)
    await db.commit()
