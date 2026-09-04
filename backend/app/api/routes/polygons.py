import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.polygon import Polygon
from app.models.user import User
from app.schemas.polygon import PolygonCreate, PolygonOut, PolygonUpdate

router = APIRouter(tags=["polygons"])


@router.get(
    "/polygons",
    response_model=list[PolygonOut],
    summary="Список полигонов для карты",
)
async def list_polygons(db: AsyncSession = Depends(get_db)) -> list[Polygon]:
    """Все зарегистрированные полигоны: открытые AOI датасета соревнования
    (`is_custom=false`) и полигоны, нарисованные пользователями (`is_custom=true`)."""
    result = await db.execute(select(Polygon).order_by(Polygon.id))
    return list(result.scalars().all())


@router.post(
    "/polygons/custom",
    response_model=PolygonOut,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать нарисованный пользователем полигон",
)
async def create_custom_polygon(
    payload: PolygonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Polygon:
    polygon = Polygon(
        id=f"custom-{uuid.uuid4().hex[:12]}",
        label=payload.label,
        crop_type=payload.crop_type,
        points=[list(p) for p in payload.points],
        is_custom=True,
        owner_id=current_user.id,
    )
    db.add(polygon)
    await db.commit()
    await db.refresh(polygon)
    return polygon


@router.get("/polygons/{polygon_id}", response_model=PolygonOut, summary="Получить один полигон")
async def get_polygon(polygon_id: str, db: AsyncSession = Depends(get_db)) -> Polygon:
    polygon = await db.get(Polygon, polygon_id)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Полигон не найден")
    return polygon


@router.put("/polygons/{polygon_id}", response_model=PolygonOut, summary="Обновить свой полигон")
async def update_polygon(
    polygon_id: str,
    payload: PolygonUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Polygon:
    polygon = await db.get(Polygon, polygon_id)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Полигон не найден")
    if not polygon.is_custom or polygon.owner_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Можно изменять только свои полигоны")

    if payload.label is not None:
        polygon.label = payload.label
    if payload.crop_type is not None:
        polygon.crop_type = payload.crop_type
    if payload.points is not None:
        polygon.points = [list(p) for p in payload.points]

    await db.commit()
    await db.refresh(polygon)
    return polygon


@router.delete(
    "/polygons/{polygon_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить свой полигон",
)
async def delete_polygon(
    polygon_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    polygon = await db.get(Polygon, polygon_id)
    if polygon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Полигон не найден")
    if not polygon.is_custom or polygon.owner_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Можно удалять только свои полигоны")

    await db.delete(polygon)
    await db.commit()
