"""Регистрация → подтверждение почты → вход (см. app/api/routes/auth.py)."""


async def test_login_before_confirmation_is_rejected(client):
    res = await client.post(
        "/auth/register",
        json={"email": "pytest@example.com", "password": "StrongPass123", "full_name": "Pytest"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "pytest@example.com"
    token = body["email_confirmation_token"]

    res = await client.post(
        "/auth/login", json={"email": "pytest@example.com", "password": "StrongPass123"}
    )
    assert res.status_code == 403

    res = await client.post("/auth/confirm-email", json={"token": token})
    assert res.status_code == 200
    assert "access_token" in res.json()

    # Токен одноразовый — повторное использование должно быть отклонено.
    res = await client.post("/auth/confirm-email", json={"token": token})
    assert res.status_code == 400

    res = await client.post(
        "/auth/login", json={"email": "pytest@example.com", "password": "StrongPass123"}
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


async def test_register_duplicate_email_is_rejected(client):
    payload = {"email": "dup@example.com", "password": "StrongPass123"}
    assert (await client.post("/auth/register", json=payload)).status_code == 201
    assert (await client.post("/auth/register", json=payload)).status_code == 400


async def test_login_with_wrong_password_is_rejected(client):
    await client.post(
        "/auth/register", json={"email": "wrongpass@example.com", "password": "StrongPass123"}
    )
    res = await client.post(
        "/auth/login", json={"email": "wrongpass@example.com", "password": "NotThisOne123"}
    )
    assert res.status_code == 401


async def test_confirm_email_with_unknown_token_is_rejected(client):
    res = await client.post("/auth/confirm-email", json={"token": "does-not-exist"})
    assert res.status_code == 400
