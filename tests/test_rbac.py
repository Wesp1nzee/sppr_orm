"""Тесты RBAC-цепочки: require_roles поверх get_current_user."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI

from app.auth.dependencies import require_roles
from app.auth.models import User, UserRole

UserFactory = Callable[..., Awaitable[User]]

ADMIN_ONLY = "/api/v1/test/admin-only"
LOGIN = "/api/v1/auth/login"


@pytest_asyncio.fixture
async def client_with_admin_route(
    app: FastAPI, client: httpx.AsyncClient
) -> httpx.AsyncClient:
    @app.get(ADMIN_ONLY)
    async def admin_only(
        user: Annotated[User, Depends(require_roles(UserRole.admin))],
    ) -> dict[str, dict[str, bool]]:
        return {"data": {"ok": True}}

    return client


@pytest.mark.asyncio
async def test_lawyer_denied_admin_route(
    client_with_admin_route: httpx.AsyncClient,
    csrf_headers: dict[str, str],
    user_factory: UserFactory,
) -> None:
    await user_factory("lawyer@example.com", "password123", UserRole.lawyer)
    login_response = await client_with_admin_route.post(
        LOGIN,
        json={"email": "lawyer@example.com", "password": "password123"},
        headers=csrf_headers,
    )
    assert login_response.status_code == 200

    response = await client_with_admin_route.get(ADMIN_ONLY)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_admin_allowed_admin_route(
    client_with_admin_route: httpx.AsyncClient,
    csrf_headers: dict[str, str],
    user_factory: UserFactory,
) -> None:
    await user_factory("admin@example.com", "password123", UserRole.admin)
    login_response = await client_with_admin_route.post(
        LOGIN,
        json={"email": "admin@example.com", "password": "password123"},
        headers=csrf_headers,
    )
    assert login_response.status_code == 200

    response = await client_with_admin_route.get(ADMIN_ONLY)
    assert response.status_code == 200
    assert response.json()["data"]["ok"] is True


@pytest.mark.asyncio
async def test_denied_route_without_session(
    client_with_admin_route: httpx.AsyncClient,
) -> None:
    response = await client_with_admin_route.get(ADMIN_ONLY)
    assert response.status_code == 401
