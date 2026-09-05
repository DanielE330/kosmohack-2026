"""CRUD своих полигонов (см. app/api/routes/polygons.py):
создание/чтение — публичные для датасета, изменение/удаление — только
владелец своего `is_custom=true` полигона (см. tasks/backend.md)."""

from app.services import region_search

_POINTS = [[47.0, 39.0], [47.0, 39.1], [47.1, 39.1]]


async def _register_and_confirm(client, email: str) -> str:
    res = await client.post("/auth/register", json={"email": email, "password": "StrongPass123"})
    token = res.json()["email_confirmation_token"]
    res = await client.post("/auth/confirm-email", json={"token": token})
    return res.json()["access_token"]


async def test_create_without_auth_is_rejected(client):
    res = await client.post("/polygons/custom", json={"points": _POINTS})
    assert res.status_code == 401


async def test_full_crud_cycle_by_owner(client):
    jwt = await _register_and_confirm(client, "owner@example.com")
    headers = {"Authorization": f"Bearer {jwt}"}

    res = await client.post(
        "/polygons/custom",
        json={"points": _POINTS, "label": "Тестовый участок", "crop_type": "тест"},
        headers=headers,
    )
    assert res.status_code == 201
    polygon = res.json()
    assert polygon["is_custom"] is True
    polygon_id = polygon["anon_polygon_id"]

    res = await client.get("/polygons", headers=headers)
    assert res.status_code == 200
    assert any(p["anon_polygon_id"] == polygon_id for p in res.json())

    res = await client.put(
        f"/polygons/{polygon_id}", json={"label": "Переименованный участок"}, headers=headers
    )
    assert res.status_code == 200
    assert res.json()["label"] == "Переименованный участок"
    assert res.json()["crop_type"] == "тест"  # не тронуто — не передавалось в PUT

    res = await client.delete(f"/polygons/{polygon_id}", headers=headers)
    assert res.status_code == 204

    res = await client.get("/polygons", headers=headers)
    assert all(p["anon_polygon_id"] != polygon_id for p in res.json())


async def test_only_owner_can_modify_or_delete(client):
    owner_jwt = await _register_and_confirm(client, "owner2@example.com")
    other_jwt = await _register_and_confirm(client, "other@example.com")

    res = await client.post(
        "/polygons/custom",
        json={"points": _POINTS, "label": "Чужой для other"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    polygon_id = res.json()["anon_polygon_id"]
    other_headers = {"Authorization": f"Bearer {other_jwt}"}

    res = await client.put(f"/polygons/{polygon_id}", json={"label": "Взлом"}, headers=other_headers)
    assert res.status_code == 403

    res = await client.delete(f"/polygons/{polygon_id}", headers=other_headers)
    assert res.status_code == 403


async def test_update_unknown_polygon_returns_404(client):
    jwt = await _register_and_confirm(client, "notfound@example.com")
    res = await client.put(
        "/polygons/does-not-exist",
        json={"label": "x"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 404


async def test_region_returns_existing_polygon_without_calling_overpass(client, monkeypatch):
    """Уже известный полигон внутри bbox — не ходим в Overpass повторно."""
    jwt = await _register_and_confirm(client, "region-existing@example.com")
    res = await client.post(
        "/polygons/custom",
        json={"points": _POINTS, "label": "В регионе"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert res.status_code == 201

    async def _fail_if_called(*args, **kwargs):
        raise AssertionError("fetch_osm_farmland не должен вызываться, если контур уже есть")

    monkeypatch.setattr(region_search, "fetch_osm_farmland", _fail_if_called)

    res = await client.get(
        "/polygons", params={"region": "46.9,38.9,47.2,39.2"}, headers={"Authorization": f"Bearer {jwt}"}
    )
    assert res.status_code == 200
    ids = [p["anon_polygon_id"] for p in res.json()]
    assert len(ids) == 1


async def test_region_fetches_and_persists_new_contours(client, monkeypatch):
    """Ничего в этой области ещё нет — идём во внешний источник и сохраняем найденное."""

    async def _fake_fetch(bbox, http_client):
        return [
            {"id": "osm-123", "label": "Найденное поле", "crop_type": None, "points": _POINTS}
        ]

    monkeypatch.setattr(region_search, "fetch_osm_farmland", _fake_fetch)

    res = await client.get("/polygons", params={"region": "46.9,38.9,47.2,39.2"})
    assert res.status_code == 200
    found = res.json()
    assert len(found) == 1
    assert found[0]["anon_polygon_id"] == "osm-123"
    assert found[0]["is_custom"] is False

    # Повторный запрос того же региона отдаёт уже сохранённый контур,
    # снова не дублируя его.
    res = await client.get("/polygons", params={"region": "46.9,38.9,47.2,39.2"})
    assert [p["anon_polygon_id"] for p in res.json()] == ["osm-123"]


async def test_region_unresolvable_returns_empty_list(client, monkeypatch):
    async def _fake_resolve(region, http_client):
        return None

    monkeypatch.setattr(region_search, "resolve_bbox", _fake_resolve)

    res = await client.get("/polygons", params={"region": "нигде-не-существующее-место"})
    assert res.status_code == 200
    assert res.json() == []
