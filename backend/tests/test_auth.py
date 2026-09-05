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


async def _registered_and_confirmed(client, email, password="StrongPass123"):
    res = await client.post("/auth/register", json={"email": email, "password": password})
    token = res.json()["email_confirmation_token"]
    res = await client.post("/auth/confirm-email", json={"token": token})
    return res.json()["access_token"]


async def test_change_password_requires_correct_old_password(client):
    access = await _registered_and_confirmed(client, "changepass@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    res = await client.post(
        "/auth/change-password",
        json={"old_password": "WrongOldPass1", "new_password": "NewStrongPass456"},
        headers=headers,
    )
    assert res.status_code == 401


async def test_change_password_requires_email_confirmation_before_taking_effect(client):
    access = await _registered_and_confirmed(client, "changepass2@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    res = await client.post(
        "/auth/change-password",
        json={"old_password": "StrongPass123", "new_password": "NewStrongPass456"},
        headers=headers,
    )
    assert res.status_code == 200
    change_token = res.json()["password_change_token"]

    # Ещё не подтверждено — старый пароль всё ещё рабочий, новый — нет.
    res = await client.post(
        "/auth/login", json={"email": "changepass2@example.com", "password": "StrongPass123"}
    )
    assert res.status_code == 200
    res = await client.post(
        "/auth/login", json={"email": "changepass2@example.com", "password": "NewStrongPass456"}
    )
    assert res.status_code == 401

    res = await client.post("/auth/confirm-password-change", json={"token": change_token})
    assert res.status_code == 204

    # Подтверждено — теперь наоборот.
    res = await client.post(
        "/auth/login", json={"email": "changepass2@example.com", "password": "NewStrongPass456"}
    )
    assert res.status_code == 200
    res = await client.post(
        "/auth/login", json={"email": "changepass2@example.com", "password": "StrongPass123"}
    )
    assert res.status_code == 401

    # Токен одноразовый.
    res = await client.post("/auth/confirm-password-change", json={"token": change_token})
    assert res.status_code == 400


async def test_confirm_password_change_with_unknown_token_is_rejected(client):
    res = await client.post("/auth/confirm-password-change", json={"token": "does-not-exist"})
    assert res.status_code == 400


async def test_change_email_requires_password_and_reconfirmation(client):
    access = await _registered_and_confirmed(client, "oldaddress@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    res = await client.post(
        "/auth/change-email",
        json={"new_email": "newaddress@example.com", "password": "WrongPass1"},
        headers=headers,
    )
    assert res.status_code == 401

    res = await client.post(
        "/auth/change-email",
        json={"new_email": "newaddress@example.com", "password": "StrongPass123"},
        headers=headers,
    )
    assert res.status_code == 200
    new_token = res.json()["email_confirmation_token"]

    # Старый JWT привязан к старому email — он больше не находится в БД.
    res = await client.post(
        "/auth/change-password",
        json={"old_password": "StrongPass123", "new_password": "Whatever123"},
        headers=headers,
    )
    assert res.status_code == 401

    # Логин по новому адресу отклоняется до подтверждения.
    res = await client.post(
        "/auth/login", json={"email": "newaddress@example.com", "password": "StrongPass123"}
    )
    assert res.status_code == 403

    res = await client.post("/auth/confirm-email", json={"token": new_token})
    assert res.status_code == 200


async def test_change_email_to_existing_address_is_rejected(client):
    await _registered_and_confirmed(client, "taken@example.com")
    access = await _registered_and_confirmed(client, "wants-taken@example.com")

    res = await client.post(
        "/auth/change-email",
        json={"new_email": "taken@example.com", "password": "StrongPass123"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert res.status_code == 400
