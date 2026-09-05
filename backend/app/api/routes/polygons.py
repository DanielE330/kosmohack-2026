import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_http_client
from app.models.polygon import Polygon
from app.models.user import User
from app.schemas.polygon import PolygonCreate, PolygonOut, PolygonUpdate
from app.services import region_search

router = APIRouter(tags=["polygons"])


@router.get(
    "/polygons",
    response_model=list[PolygonOut],
    summary="Список полигонов для карты",
)
async def list_polygons(
    region: str | None = Query(
        None,
        description=(
            "Bbox `lat1,lon1,lat2,lon2` или название региона — автопоиск доступных "
            "сельхозконтуров (OSM) для новой территории, а не только статический список"
        ),
        examples=["47.0,39.0,47.2,39.3"],
    ),
    db: AsyncSession = Depends(get_db),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> list[Polygon]:
    """Все зарегистрированные полигоны: открытые AOI датасета соревнования
    (`is_custom=false`) и полигоны, нарисованные пользователями (`is_custom=true`).

    С параметром `region` — сначала отдаём уже известные полигоны, чей
    центроид попадает в эту область (повторный поиск не плодит дублей),
    а если таких нет — находим открытые сельхозконтуры через Overpass
    (OSM: landuse=farmland/orchard/vineyard/meadow), сохраняем их как
    несобственные полигоны (`is_custom=false`) и возвращаем."""
    result = await db.execute(select(Polygon).order_by(Polygon.id))
    all_polygons = list(result.scalars().all())

    if region is None:
        return all_polygons

    bbox = await region_search.resolve_bbox(region, http_client)
    if bbox is None:
        return []

    in_bbox = [p for p in all_polygons if region_search.centroid_in_bbox(p.points, bbox)]
    if in_bbox:
        return in_bbox

    existing_ids = {p.id for p in all_polygons}
    found = await region_search.fetch_osm_farmland(bbox, http_client)
    new_polygons = [
        Polygon(
            id=item["id"],
            label=item["label"],
            crop_type=item["crop_type"],
            points=item["points"],
            is_custom=False,
        )
        for item in found
        if item["id"] not in existing_ids
    ]
    if not new_polygons:
        return []

    db.add_all(new_polygons)
    await db.commit()
    for polygon in new_polygons:
        await db.refresh(polygon)
    return new_polygons


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
