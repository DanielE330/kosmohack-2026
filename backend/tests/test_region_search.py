"""Юнит-тесты чистых функций `app/services/region_search.py`
(парсинг bbox, попадание центроида в область) — без сети и без БД.
Поход в Overpass/Nominatim здесь не тестируется живым запросом (внешний
сервис недоступен/нестабилен в CI) — см. `test_polygons.py` для
эндпоинт-теста с замоканным `fetch_osm_farmland`."""

from app.services import region_search


def test_parse_bbox_normalizes_order():
    bbox = region_search.parse_bbox("47.2,39.3,47.0,39.0")
    assert bbox == (47.0, 39.0, 47.2, 39.3)


def test_parse_bbox_rejects_non_bbox_text():
    assert region_search.parse_bbox("Ростовская область") is None
    assert region_search.parse_bbox("1,2,3") is None
    assert region_search.parse_bbox("a,b,c,d") is None


def test_centroid_in_bbox():
    bbox = (47.0, 39.0, 47.2, 39.3)
    inside = [[47.05, 39.05], [47.1, 39.1], [47.05, 39.15]]
    outside = [[10.0, 10.0], [10.1, 10.1], [10.05, 10.2]]
    assert region_search.centroid_in_bbox(inside, bbox) is True
    assert region_search.centroid_in_bbox(outside, bbox) is False
    assert region_search.centroid_in_bbox([], bbox) is False
