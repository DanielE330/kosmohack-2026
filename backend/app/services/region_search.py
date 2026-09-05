"""Автопоиск открытых сельхозконтуров по региону — `GET /polygons?region=...`
(см. `tasks/backend.md`, п.4, и критерий «Управление полигонами» в
`docs/criteria.pdf`: сервис должен сам находить доступные контуры при
выборе нового региона, не только принимать клики пользователя).

Источник контуров — Overpass API (OpenStreetMap): участки с
`landuse=farmland/orchard/vineyard/meadow`. Полноценный ESA WorldCereal
здесь не подключён — он отдаёт растровую классификацию через
GEE/STAC и требует отдельных доступов/инфраструктуры, а для задачи
«показать на карте контуры, по которым можно кликнуть» векторных
контуров OSM достаточно и не нужны ключи/аккаунты.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim требует идентифицирующий User-Agent (Usage Policy), без email.
_USER_AGENT = "vegmon-hackathon-backend/0.1 (kosmohack-2026)"

_LANDUSE_TAGS = ("farmland", "orchard", "vineyard", "meadow")
_MAX_FEATURES = 20
_MAX_NODES_PER_WAY = 500

BBox = tuple[float, float, float, float]  # (min_lat, min_lon, max_lat, max_lon)


def parse_bbox(region: str) -> BBox | None:
    """`"lat1,lon1,lat2,lon2"` -> bbox с отсортированными границами.
    None, если строка не похожа на bbox (тогда пробуем геокодировать как название)."""
    parts = region.split(",")
    if len(parts) != 4:
        return None
    try:
        lat1, lon1, lat2, lon2 = (float(p) for p in parts)
    except ValueError:
        return None
    return min(lat1, lat2), min(lon1, lon2), max(lat1, lat2), max(lon1, lon2)


async def resolve_bbox(region: str, client: httpx.AsyncClient) -> BBox | None:
    """Bbox из параметра `region`: координаты — сразу, иначе геокодируем
    название региона через Nominatim (OSM). None, если ни то, ни другое
    не сработало (регион не найден / сервис недоступен)."""
    bbox = parse_bbox(region)
    if bbox is not None:
        return bbox

    try:
        resp = await client.get(
            NOMINATIM_URL,
            params={"q": region, "format": "json", "limit": 1},
            headers={"User-Agent": _USER_AGENT},
            timeout=10.0,
        )
        resp.raise_for_status()
        results = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Nominatim geocoding failed for %r: %s", region, exc)
        return None

    if not results:
        return None
    south, north, west, east = (float(x) for x in results[0]["boundingbox"])
    return south, west, north, east


def centroid_in_bbox(points: list[list[float]], bbox: BBox) -> bool:
    """Попадает ли центроид контура в bbox — так уже сохранённые полигоны
    находятся повторным поиском без похода в Overpass заново."""
    if not points:
        return False
    min_lat, min_lon, max_lat, max_lon = bbox
    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def _way_to_points(way: dict, nodes_by_id: dict[int, tuple[float, float]]) -> list[list[float]] | None:
    node_ids = way.get("nodes") or []
    if not node_ids or len(node_ids) > _MAX_NODES_PER_WAY:
        return None
    points = [nodes_by_id[n] for n in node_ids if n in nodes_by_id]
    if len(points) < 3:
        return None
    if points[0] == points[-1]:  # Overpass отдаёт замкнутое кольцо
        points = points[:-1]
    return [[lat, lon] for lat, lon in points]


async def fetch_osm_farmland(bbox: BBox, client: httpx.AsyncClient) -> list[dict]:
    """Ищет открытые сельхозконтуры в bbox через Overpass API. Возвращает
    список словарей `{id, label, crop_type, points}`, готовых стать
    записью `Polygon` (`is_custom=False`, без владельца). Пустой список,
    если Overpass недоступен или ничего не нашлось — вызывающий код не
    должен падать из-за недоступности стороннего сервиса."""
    min_lat, min_lon, max_lat, max_lon = bbox
    tag_filter = "".join(
        f'way["landuse"="{tag}"]({min_lat},{min_lon},{max_lat},{max_lon});' for tag in _LANDUSE_TAGS
    )
    query = f"[out:json][timeout:20];({tag_filter});out body;>;out skel qt;"

    try:
        resp = await client.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": _USER_AGENT},
            timeout=25.0,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Overpass request failed for bbox %s: %s", bbox, exc)
        return []

    elements = payload.get("elements", [])
    nodes_by_id = {el["id"]: (el["lat"], el["lon"]) for el in elements if el.get("type") == "node"}
    ways = [el for el in elements if el.get("type") == "way"]

    found = []
    for way in ways[:_MAX_FEATURES]:
        points = _way_to_points(way, nodes_by_id)
        if points is None:
            continue
        tags = way.get("tags", {})
        found.append(
            {
                "id": f"osm-{way['id']}",
                "label": tags.get("name"),
                "crop_type": tags.get("crop"),
                "points": points,
            }
        )
    return found
