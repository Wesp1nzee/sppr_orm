"""Тесты rate limiting на аутентификационных эндпоинтах (защита от брутфорса)."""

import httpx
import pytest

from app.core.config import get_settings

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/register"

PASSWORD = "strong-password-123"


@pytest.mark.asyncio
async def test_login_rate_limited_after_limit(
    client: httpx.AsyncClient, csrf_headers: dict[str, str]
) -> None:
    settings = get_settings()
    for _ in range(settings.rate_limit_login_per_minute):
        response = await client.post(
            LOGIN,
            json={"email": "bruteforce@example.com", "password": "wrong-password"},
            headers=csrf_headers,
        )
        assert response.status_code == 401

    response = await client.post(
        LOGIN,
        json={"email": "bruteforce@example.com", "password": "wrong-password"},
        headers=csrf_headers,
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_register_rate_limited_after_limit(
    client: httpx.AsyncClient, csrf_headers: dict[str, str]
) -> None:
    settings = get_settings()
    for i in range(settings.rate_limit_register_per_minute):
        response = await client.post(
            REGISTER,
            json={
                "email": f"bruteforce-{i}@example.com",
                "password": PASSWORD,
                "full_name": "Брутфорс Тест",
                "role": "lawyer",
            },
            headers=csrf_headers,
        )
        assert response.status_code == 201

    response = await client.post(
        REGISTER,
        json={
            "email": "bruteforce-final@example.com",
            "password": PASSWORD,
            "full_name": "Брутфорс Тест",
            "role": "lawyer",
        },
        headers=csrf_headers,
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
