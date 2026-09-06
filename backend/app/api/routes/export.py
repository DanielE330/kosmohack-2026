"""Выгрузка данных по участкам в Excel (.xlsx) и zip-архив.

Собирается на бэкенде, а не во фронте: только здесь есть все поля
наблюдения (ряды ДЗЗ, ERA5, климатическая норма) и периоды аномалий, а
клиенту остаётся скачать готовый файл. Заголовки колонок — русские, с
единицами измерения (см. `app/services/excel_export.py`).
"""

from datetime import date as date_type
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional, get_db
from app.models.anomaly import AnomalyPeriod
from app.models.polygon import Polygon
from app.models.timeseries import NdviObservation
from app.models.user import User
from app.services import excel_export
from app.services import maps as maps_service

router = APIRouter(prefix="/export", tags=["export"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ZIP_MEDIA_TYPE = "application/zip"


def _content_disposition(filename: str) -> str:
    """Имя файла в заголовке — только в RFC 5987-форме (`filename*`): оно
    кириллическое, а обычный `filename=` допускает лишь latin-1, и браузер
    на нём ломается либо отдаёт файл как «download»."""
    return f"attachment; filename=\"export.xlsx\"; filename*=UTF-8''{quote(filename)}"


async def _accessible_map_ids(db: AsyncSession, current_user: User | None) -> set[int]:
    if current_user is None:
        return set()
    return {m.id for m in await maps_service.list_accessible_maps(db, current_user)}


def _is_visible(polygon: Polygon, accessible_map_ids: set[int]) -> bool:
    """Та же видимость, что и в `GET /polygons`: открытые сидовые полигоны
    датасета (`map_id IS NULL`) — всем, полигоны на чьей-то карте — только
    участникам этой карты. Дублируем правило здесь, чтобы не тащить
    приватную функцию из routes/polygons.py."""
    return polygon.map_id is None or polygon.map_id in accessible_map_ids


async def _load_bundles(
    db: AsyncSession,
    polygons: list[Polygon],
    date_from: date_type | None,
    date_to: date_type | None,
) -> list[excel_export.PolygonExport]:
    """Наблюдения и аномалии сразу по всем запрошенным участкам — одним
    запросом на каждую таблицу, а не по запросу на полигон (тот же приём,
    что и в `GET /polygons/with-timeseries`)."""
    ids = [p.id for p in polygons]
    if not ids:
        return []

    obs_stmt = (
        select(NdviObservation)
        .where(NdviObservation.polygon_id.in_(ids))
        .order_by(NdviObservation.polygon_id, NdviObservation.date)
    )
    if date_from is not None:
        obs_stmt = obs_stmt.where(NdviObservation.date >= date_from)
    if date_to is not None:
        obs_stmt = obs_stmt.where(NdviObservation.date <= date_to)
    observations = list((await db.execute(obs_stmt)).scalars().all())

    anomalies = list(
        (
            await db.execute(
                select(AnomalyPeriod)
                .where(AnomalyPeriod.polygon_id.in_(ids))
                .order_by(AnomalyPeriod.polygon_id, AnomalyPeriod.start_date)
            )
        )
        .scalars()
        .all()
    )

    obs_by_polygon: dict[str, list[NdviObservation]] = {pid: [] for pid in ids}
    for obs in observations:
        obs_by_polygon[obs.polygon_id].append(obs)
    anomalies_by_polygon: dict[str, list[AnomalyPeriod]] = {pid: [] for pid in ids}
    for anomaly in anomalies:
        anomalies_by_polygon[anomaly.polygon_id].append(anomaly)

    return [
        excel_export.PolygonExport(p, obs_by_polygon[p.id], anomalies_by_polygon[p.id])
        for p in polygons
    ]


async def _resolve_polygons(
    db: AsyncSession,
    ids: list[str] | None,
    map_id: int | None,
    current_user: User | None,
) -> list[Polygon]:
    accessible_map_ids = await _accessible_map_ids(db, current_user)
    stmt = select(Polygon).order_by(Polygon.id)
    if ids:
        stmt = stmt.where(Polygon.id.in_(ids))
    if map_id is not None:
        stmt = stmt.where(Polygon.map_id == map_id)
    found = [p for p in (await db.execute(stmt)).scalars().all() if _is_visible(p, accessible_map_ids)]

    if ids:
        # Порядок — как перечислил клиент (порядок строк в его таблице),
        # а не алфавитный по id.
        by_id = {p.id: p for p in found}
        missing = [pid for pid in ids if pid not in by_id]
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Полигоны не найдены или недоступны: {', '.join(missing)}",
            )
        return [by_id[pid] for pid in ids]

    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Нет доступных полигонов для выгрузки")
    return found


_IDS_QUERY = Query(
    None,
    alias="ids",
    description="Идентификаторы полигонов; можно повторять параметр или перечислить через запятую. "
    "Без параметра — все видимые пользователю полигоны",
    examples=[["AOI-0002", "AOI-0003"]],
)


def _normalize_ids(ids: list[str] | None) -> list[str] | None:
    """`?ids=a&ids=b` и `?ids=a,b` — обе формы, чтобы фронту не приходилось
    собирать длинный query вручную."""
    if not ids:
        return None
    flat = [part.strip() for raw in ids for part in raw.split(",") if part.strip()]
    return flat or None


@router.get(
    "/polygon/{polygon_id}.xlsx",
    summary="Excel-выгрузка по одному участку",
    response_class=Response,
    responses={200: {"content": {XLSX_MEDIA_TYPE: {}}, "description": "Книга Excel: сводка, наблюдения, аномалии"}},
)
async def export_polygon_xlsx(
    polygon_id: str,
    date_from: date_type | None = Query(None, description="Только наблюдения с этой даты"),
    date_to: date_type | None = Query(None, description="Только наблюдения по эту дату включительно"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> Response:
    polygon = await db.get(Polygon, polygon_id)
    if polygon is None or not _is_visible(polygon, await _accessible_map_ids(db, current_user)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Полигон не найден")

    bundles = await _load_bundles(db, [polygon], date_from, date_to)
    content = excel_export.build_polygon_workbook(bundles[0])
    filename = f"{excel_export.file_stem(polygon)} — {date_type.today():%Y-%m-%d}.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@router.get(
    "/polygons.xlsx",
    summary="Excel-выгрузка по нескольким участкам одной книгой",
    response_class=Response,
    responses={200: {"content": {XLSX_MEDIA_TYPE: {}}, "description": "Книга Excel: лист на каждый участок"}},
)
async def export_polygons_xlsx(
    ids: list[str] | None = _IDS_QUERY,
    map_id: int | None = Query(None, description="Все полигоны конкретной карты"),
    date_from: date_type | None = Query(None),
    date_to: date_type | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> Response:
    polygons = await _resolve_polygons(db, _normalize_ids(ids), map_id, current_user)
    bundles = await _load_bundles(db, polygons, date_from, date_to)
    content = excel_export.build_combined_workbook(bundles)
    filename = f"Участки — {date_type.today():%Y-%m-%d}.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@router.get(
    "/polygons.zip",
    summary="Zip с отдельным Excel-файлом на каждый участок",
    response_class=Response,
    responses={200: {"content": {ZIP_MEDIA_TYPE: {}}, "description": "Архив .xlsx-файлов + общая сводка"}},
)
async def export_polygons_zip(
    ids: list[str] | None = _IDS_QUERY,
    map_id: int | None = Query(None, description="Все полигоны конкретной карты"),
    date_from: date_type | None = Query(None),
    date_to: date_type | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> Response:
    polygons = await _resolve_polygons(db, _normalize_ids(ids), map_id, current_user)
    bundles = await _load_bundles(db, polygons, date_from, date_to)
    content = excel_export.build_zip(bundles)
    filename = f"Отчёт SkyTime — {date_type.today():%Y-%m-%d}.zip"
    return Response(
        content=content,
        media_type=ZIP_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"skytime-report.zip\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )
