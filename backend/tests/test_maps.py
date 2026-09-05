"""Карты (`Map`/`MapMember`, см. app/api/routes/maps.py, app/services/maps.py):
владелец может создать карту, пригласить другого зарегистрированного
пользователя (viewer по умолчанию, можно editor), viewer может только
читать полигоны карты, editor — ещё и создавать/удалять их."""

_POINTS = [[47.0, 39.0], [47.0, 39.1], [47.1, 39.1]]


async def _register_and_confirm(client, email: str) -> str:
    res = await client.post("/auth/register", json={"email": email, "password": "StrongPass123"})
    token = res.json()["email_confirmation_token"]
    res = await client.post("/auth/confirm-email", json={"token": token})
    return res.json()["access_token"]


def _auth(jwt: str) -> dict:
    return {"Authorization": f"Bearer {jwt}"}


async def test_create_map_and_default_personal_map_on_first_polygon(client):
    jwt = await _register_and_confirm(client, "owner@example.com")

    res = await client.post("/polygons/custom", json={"points": _POINTS}, headers=_auth(jwt))
    assert res.status_code == 201
    assert res.json()["map_id"] is not None

    res = await client.get("/maps", headers=_auth(jwt))
    assert res.status_code == 200
    maps = res.json()
    assert len(maps) == 1
    assert maps[0]["role"] == "owner"

    res = await client.post("/maps", json={"name": "Вторая карта"}, headers=_auth(jwt))
    assert res.status_code == 201
    assert res.json()["name"] == "Вторая карта"

    res = await client.get("/maps", headers=_auth(jwt))
    assert len(res.json()) == 2


async def test_invite_unknown_email_is_rejected(client):
    jwt = await _register_and_confirm(client, "owner2@example.com")
    res = await client.post("/maps", json={"name": "Карта"}, headers=_auth(jwt))
    map_id = res.json()["id"]

    res = await client.post(
        "/maps/{}/invite".format(map_id),
        json={"email": "nobody@example.com"},
        headers=_auth(jwt),
    )
    assert res.status_code == 404


async def test_viewer_can_read_but_not_create_or_delete(client):
    owner_jwt = await _register_and_confirm(client, "map-owner@example.com")
    viewer_jwt = await _register_and_confirm(client, "map-viewer@example.com")

    res = await client.post("/maps", json={"name": "Общая карта"}, headers=_auth(owner_jwt))
    map_id = res.json()["id"]

    res = await client.post(
        f"/maps/{map_id}/invite", json={"email": "map-viewer@example.com"}, headers=_auth(owner_jwt)
    )
    assert res.status_code == 200
    assert res.json()["role"] == "viewer"

    # Viewer видит карту в своём списке и видит (пустой) список полигонов.
    res = await client.get("/maps", headers=_auth(viewer_jwt))
    assert any(m["id"] == map_id and m["role"] == "viewer" for m in res.json())

    res = await client.get("/polygons", params={"map_id": map_id}, headers=_auth(viewer_jwt))
    assert res.status_code == 200
    assert res.json() == []

    # Viewer не может создавать полигоны на этой карте.
    res = await client.post(
        "/polygons/custom",
        json={"points": _POINTS, "map_id": map_id},
        headers=_auth(viewer_jwt),
    )
    assert res.status_code == 403

    # Владелец создаёт полигон — viewer теперь его видит, но не может удалить.
    res = await client.post(
        "/polygons/custom", json={"points": _POINTS, "map_id": map_id}, headers=_auth(owner_jwt)
    )
    polygon_id = res.json()["anon_polygon_id"]

    res = await client.get("/polygons", params={"map_id": map_id}, headers=_auth(viewer_jwt))
    assert len(res.json()) == 1

    res = await client.delete(f"/polygons/{polygon_id}", headers=_auth(viewer_jwt))
    assert res.status_code == 403


async def test_editor_can_create_and_delete_on_shared_map(client):
    owner_jwt = await _register_and_confirm(client, "map-owner2@example.com")
    editor_jwt = await _register_and_confirm(client, "map-editor@example.com")

    res = await client.post("/maps", json={"name": "Совместная карта"}, headers=_auth(owner_jwt))
    map_id = res.json()["id"]

    res = await client.post(
        f"/maps/{map_id}/invite",
        json={"email": "map-editor@example.com", "role": "editor"},
        headers=_auth(owner_jwt),
    )
    assert res.status_code == 200
    assert res.json()["role"] == "editor"

    res = await client.post(
        "/polygons/custom", json={"points": _POINTS, "map_id": map_id}, headers=_auth(editor_jwt)
    )
    assert res.status_code == 201
    polygon_id = res.json()["anon_polygon_id"]

    res = await client.delete(f"/polygons/{polygon_id}", headers=_auth(editor_jwt))
    assert res.status_code == 204


async def test_non_member_cannot_see_or_use_map(client):
    owner_jwt = await _register_and_confirm(client, "map-owner3@example.com")
    outsider_jwt = await _register_and_confirm(client, "outsider@example.com")

    res = await client.post("/maps", json={"name": "Приватная карта"}, headers=_auth(owner_jwt))
    map_id = res.json()["id"]

    res = await client.get("/polygons", params={"map_id": map_id}, headers=_auth(outsider_jwt))
    assert res.status_code == 404

    res = await client.post(
        "/polygons/custom", json={"points": _POINTS, "map_id": map_id}, headers=_auth(outsider_jwt)
    )
    assert res.status_code == 403

    # Полигоны приватной карты не должны утекать в общий список без фильтра.
    await client.post("/polygons/custom", json={"points": _POINTS, "map_id": map_id}, headers=_auth(owner_jwt))
    res = await client.get("/polygons", headers=_auth(outsider_jwt))
    assert all(p["map_id"] != map_id for p in res.json())


async def test_owner_can_revoke_member_access(client):
    owner_jwt = await _register_and_confirm(client, "map-owner4@example.com")
    member_jwt = await _register_and_confirm(client, "map-member@example.com")

    res = await client.post("/maps", json={"name": "Карта с ревокацией"}, headers=_auth(owner_jwt))
    map_id = res.json()["id"]

    await client.post(
        f"/maps/{map_id}/invite", json={"email": "map-member@example.com"}, headers=_auth(owner_jwt)
    )
    res = await client.get("/maps", headers=_auth(member_jwt))
    assert any(m["id"] == map_id for m in res.json())

    # Найдём user_id участника через список карт нет — воспользуемся /maps/{id}/members.
    res = await client.get(f"/maps/{map_id}/members", headers=_auth(owner_jwt))
    member_user_id = res.json()[0]["user_id"]

    res = await client.delete(f"/maps/{map_id}/members/{member_user_id}", headers=_auth(owner_jwt))
    assert res.status_code == 204

    res = await client.get("/maps", headers=_auth(member_jwt))
    assert all(m["id"] != map_id for m in res.json())

    res = await client.get("/polygons", params={"map_id": map_id}, headers=_auth(member_jwt))
    assert res.status_code == 404
