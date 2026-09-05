"""GET /polygons/{id}/live-sources — живой сбор данных из Google Earth
Engine (Sentinel-2/Landsat/MODIS/ERA5), см. app/services/gee_bridge.py.
Тесты не ходят в реальный GEE (нет кредов в CI) — проверяют только, что
без настроенного `EARTHENGINE_PROJECT` сервис отдаёт понятную 503, а не
падает и не отдаёт частичный мусор (см. критерий «устойчивость к частичной
недоступности данных»)."""

_POINTS = [[47.0, 39.0], [47.0, 39.1], [47.1, 39.1]]


async def _create_polygon(client) -> str:
    reg = await client.post(
        "/auth/register", json={"email": "gee-test@example.com", "password": "StrongPass123"}
    )
    token = reg.json()["email_confirmation_token"]
    confirm = await client.post("/auth/confirm-email", json={"token": token})
    jwt = confirm.json()["access_token"]

    created = await client.post(
        "/polygons/custom",
        json={"points": _POINTS},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    return created.json()["anon_polygon_id"]


async def test_live_sources_without_gee_config_returns_503(client):
    polygon_id = await _create_polygon(client)
    res = await client.get(
        f"/polygons/{polygon_id}/live-sources",
        params={"date_from": "2024-01-01", "date_to": "2024-02-01"},
    )
    assert res.status_code == 503


async def test_live_sources_for_unknown_polygon_is_404(client):
    res = await client.get(
        "/polygons/does-not-exist/live-sources",
        params={"date_from": "2024-01-01", "date_to": "2024-02-01"},
    )
    assert res.status_code == 404
