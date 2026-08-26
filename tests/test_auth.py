"""Интеграционные тесты auth-флоу: регистрация, логин, logout, сессии."""

from __future__ import annotations

import json
import time

import httpx
import pytest

from app.auth.models import UserRole
from app.auth.service import session_key

EMAIL = "user@example.com"
PASSWORD = "strong-password-123"
FULL_NAME = "Иван Иванов"

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


async def register(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    email: str = EMAIL,
    password: str = PASSWORD,
    role: str = "lawyer",
) -> httpx.Response:
    return await client.post(
        REGISTER,
        json={
            "email": email,
            "password": password,
            "full_name": FULL_NAME,
            "role": role,
        },
        headers=headers,
    )


async def login(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    email: str = EMAIL,
    password: str = PASSWORD,
) -> httpx.Response:
    return await client.post(
        LOGIN, json={"email": email, "password": password}, headers=headers
    )


@pytest.mark.asyncio
async def test_register_success(client, csrf_headers):
    response = await register(client, csrf_headers)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["email"] == EMAIL
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict(client, csrf_headers):
    assert (await register(client, csrf_headers)).status_code == 201
    response = await register(client, csrf_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.asyncio
async def test_register_admin_forbidden(client, csrf_headers):
    response = await register(client, csrf_headers, role="admin")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_SELF_REGISTRATION_FORBIDDEN"


@pytest.mark.asyncio
async def test_login_success_sets_cookies(client, csrf_headers):
    await register(client, csrf_headers)
    response = await login(client, csrf_headers)
    assert response.status_code == 200
    assert client.cookies.get("sid") is not None
    assert client.cookies.get("csrf_token") is not None
    assert response.json()["data"]["csrf_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(client, csrf_headers):
    await register(client, csrf_headers)
    response = await login(client, csrf_headers, password="wrong-password")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_inactive_user_forbidden(client, csrf_headers, user_factory):
    await user_factory(
        "inactive@example.com", PASSWORD, UserRole.lawyer, is_active=False
    )
    response = await login(client, csrf_headers, email="inactive@example.com")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"


@pytest.mark.asyncio
async def test_me_without_session_401(client):
    response = await client.get(ME)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_error_message_localized_by_accept_language(client):
    response = await client.get(ME, headers={"Accept-Language": "en-US,en;q=0.9"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert response.json()["error"]["message"] == (
        "Session not found or expired, please sign in"
    )


@pytest.mark.asyncio
async def test_me_with_valid_session(client, csrf_headers):
    await register(client, csrf_headers)
    await login(client, csrf_headers)
    response = await client.get(ME)
    assert response.status_code == 200
    assert response.json()["data"]["email"] == EMAIL


@pytest.mark.asyncio
async def test_session_ttl_issued_and_sliding(client, csrf_headers, fake_redis):
    await register(client, csrf_headers)
    await login(client, csrf_headers)
    sid = client.cookies.get("sid")
    assert sid is not None
    key = session_key(sid)
    ttl = await fake_redis.ttl(key)
    assert 1700 < ttl <= 1800

    # Принудительно срезаем TTL и проверяем скользящее продление на /me.
    await fake_redis.expire(key, 60)
    assert (await client.get(ME)).status_code == 200
    ttl = await fake_redis.ttl(key)
    assert 1700 < ttl <= 1800


@pytest.mark.asyncio
async def test_hard_expire_returns_401_and_deletes_key(client, csrf_headers, fake_redis):
    await register(client, csrf_headers)
    await login(client, csrf_headers)
    sid = client.cookies.get("sid")
    assert sid is not None
    key = session_key(sid)

    payload = json.loads(await fake_redis.get(key))
    payload["hard_expire_at"] = time.time() - 10
    await fake_redis.set(key, json.dumps(payload))

    response = await client.get(ME)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert await fake_redis.exists(key) == 0


@pytest.mark.asyncio
async def test_corrupted_session_401_and_deleted(client, csrf_headers, fake_redis):
    await register(client, csrf_headers)
    await login(client, csrf_headers)
    sid = client.cookies.get("sid")
    assert sid is not None
    key = session_key(sid)

    await fake_redis.set(key, "{not-json")

    response = await client.get(ME)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
    assert await fake_redis.exists(key) == 0


@pytest.mark.asyncio
async def test_logout_destroys_session_and_cookies(client, csrf_headers):
    await register(client, csrf_headers)
    login_response = await login(client, csrf_headers)
    csrf = login_response.json()["data"]["csrf_token"]

    response = await client.post(LOGOUT, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert client.cookies.get("sid") is None
    assert (await client.get(ME)).status_code == 401
