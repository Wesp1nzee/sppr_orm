"""Тесты подписанного double-submit CSRF: токен привязан к sid сессии."""

from __future__ import annotations

import httpx
import pytest

from app.core.csrf import generate_csrf_token

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
CSRF_ENDPOINT = "/api/v1/auth/csrf-token"

EMAIL = "csrf@example.com"
PASSWORD = "strong-password-123"


async def _register_and_login(
    client: httpx.AsyncClient, csrf_headers: dict[str, str]
) -> httpx.Response:
    await client.post(
        REGISTER,
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "full_name": "Ксрф Тест",
            "role": "lawyer",
        },
        headers=csrf_headers,
    )
    return await client.post(
        LOGIN,
        json={"email": EMAIL, "password": PASSWORD},
        headers=csrf_headers,
    )


@pytest.mark.asyncio
async def test_login_issues_session_bound_csrf(client, csrf_headers):
    response = await _register_and_login(client, csrf_headers)
    assert response.status_code == 200
    sid = client.cookies.get("sid")
    assert sid is not None
    assert response.json()["data"]["csrf_token"] == generate_csrf_token(sid)


@pytest.mark.asyncio
async def test_csrf_token_endpoint_binds_to_current_session(client, csrf_headers):
    await _register_and_login(client, csrf_headers)
    sid = client.cookies.get("sid")
    assert sid is not None

    response = await client.get(CSRF_ENDPOINT)
    assert response.status_code == 200
    assert response.json()["data"]["csrf_token"] == generate_csrf_token(sid)


@pytest.mark.asyncio
async def test_cookie_injection_rejected(client, csrf_headers):
    """Подмена cookie без валидного HMAC для текущего sid → 403.

    Атакующий подсовывает согласованную пару cookie == header, но токен
    вычислен для чужого sid — наивный double-submit пропустил бы такой
    запрос, подписанный — отклоняет.
    """
    await _register_and_login(client, csrf_headers)
    assert client.cookies.get("sid") is not None

    forged = generate_csrf_token("attacker-sid")
    client.cookies.set("csrf_token", forged)

    response = await client.post(LOGOUT, headers={"X-CSRF-Token": forged})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_missing_csrf_header_rejected(client, csrf_headers):
    await client.get(CSRF_ENDPOINT)  # cookie есть, заголовка нет
    response = await client.post(
        REGISTER,
        json={
            "email": "no-header@example.com",
            "password": PASSWORD,
            "full_name": "Без Заголовка",
            "role": "lawyer",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_valid_session_bound_token_accepted(client, csrf_headers):
    login_response = await _register_and_login(client, csrf_headers)
    token = login_response.json()["data"]["csrf_token"]

    response = await client.post(LOGOUT, headers={"X-CSRF-Token": token})
    assert response.status_code == 200
