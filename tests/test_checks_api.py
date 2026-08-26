"""Интеграционные тесты API домена «Проверки» (ТЗ, раздел 13)."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.auth.models import UserRole
from app.checks.models import Check

CHECKS = "/api/v1/checks"
LOGIN = "/api/v1/auth/login"
PASSWORD = "strong-password-123"

VALID_ANSWERS = {
    "criterion_1": {"has_crime_signs": True, "has_instruction": True},
    "criterion_2": {"limits_constitutional_rights": True, "has_court_order": True},
}


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    """Входит под ``email``, возвращая CSRF-заголовок новой сессии.

    Перед входом берётся свежий CSRF-токен, привязанный к текущей сессии,
    чтобы повторные входы (смена пользователя) не падали на CSRF-проверке.
    """
    csrf_resp = await client.get("/api/v1/auth/csrf-token")
    csrf_token = csrf_resp.json()["data"]["csrf_token"]

    resp = await client.post(
        LOGIN,
        json={"email": email, "password": PASSWORD},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 200
    return {"X-CSRF-Token": resp.json()["data"]["csrf_token"]}


async def _create_check(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    answers: dict | None = None,
    case_title: str | None = None,
) -> httpx.Response:
    return await client.post(
        CHECKS,
        json={"case_title": case_title, "answers": answers or {}},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_anonymous_create_returns_401(client, csrf_headers):
    response = await client.post(CHECKS, json={"answers": {}}, headers=csrf_headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_anonymous_list_returns_401(client):
    response = await client.get(CHECKS)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [
        UserRole.lawyer,
        UserRole.investigator,
        UserRole.officer,
        UserRole.admin,
    ],
)
@pytest.mark.asyncio
async def test_any_role_can_create_check(client, user_factory, role):
    email = f"{role.value}@example.com"
    await user_factory(email, PASSWORD, role)
    headers = await _login(client, email)

    response = await _create_check(client, headers)
    assert response.status_code == 201

    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["summary"] == {
        "total": 14,
        "passed": 11,
        "violations": 2,
        "attention": 1,
    }
    assert len(data["results"]) == 14


@pytest.mark.asyncio
async def test_create_check_response_envelope(client, user_factory):
    await user_factory("env@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "env@example.com")

    response = await _create_check(client, headers, answers=VALID_ANSWERS)
    assert response.status_code == 201

    body = response.json()
    assert set(body.keys()) == {"data"}
    data = body["data"]
    assert set(data.keys()) >= {
        "id",
        "status",
        "summary",
        "priority_criteria_numbers",
        "results",
    }


@pytest.mark.asyncio
async def test_priority_criteria_for_lawyer(client, user_factory):
    await user_factory("prio@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "prio@example.com")

    response = await _create_check(client, headers)
    data = response.json()["data"]
    assert data["priority_criteria_numbers"] == [2, 5, 6, 9, 10, 13]
    for result in data["results"]:
        assert result["priority_for_role"] == (
            result["criterion_number"] in {2, 5, 6, 9, 10, 13}
        )


@pytest.mark.asyncio
async def test_check_persisted_to_db(client, user_factory, session_factory):
    user = await user_factory("db@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "db@example.com")

    response = await _create_check(
        client, headers, answers=VALID_ANSWERS, case_title="Дело"
    )
    check_id = uuid.UUID(response.json()["data"]["id"])

    async with session_factory() as session:
        check = await session.get(Check, check_id)
        assert check is not None
        assert check.user_id == user.id
        assert check.case_title == "Дело"
        assert check.status == "completed"
        assert len(check.results) == 14


@pytest.mark.asyncio
async def test_user_sees_only_own_checks(client, user_factory):
    await user_factory("a@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("b@example.com", PASSWORD, UserRole.lawyer)

    headers_a = await _login(client, "a@example.com")
    await _create_check(client, headers_a, case_title="Проверка A")

    headers_b = await _login(client, "b@example.com")
    await _create_check(client, headers_b, case_title="Проверка B")

    response_b = await client.get(CHECKS)
    items_b = response_b.json()["data"]
    assert len(items_b) == 1
    assert items_b[0]["case_title"] == "Проверка B"

    headers_a = await _login(client, "a@example.com")
    response_a = await client.get(CHECKS)
    items_a = response_a.json()["data"]
    assert len(items_a) == 1
    assert items_a[0]["case_title"] == "Проверка A"


@pytest.mark.asyncio
async def test_admin_sees_all_checks(client, user_factory):
    await user_factory("law@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)

    headers_law = await _login(client, "law@example.com")
    await _create_check(client, headers_law, case_title="Проверка адвоката")

    await _login(client, "admin@example.com")
    response = await client.get(CHECKS)
    items = response.json()["data"]
    assert len(items) == 1
    assert items[0]["case_title"] == "Проверка адвоката"


@pytest.mark.asyncio
async def test_foreign_check_returns_404(client, user_factory):
    await user_factory("owner@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("stranger@example.com", PASSWORD, UserRole.lawyer)

    headers_owner = await _login(client, "owner@example.com")
    created = await _create_check(client, headers_owner)
    check_id = created.json()["data"]["id"]

    await _login(client, "stranger@example.com")
    response = await client.get(f"{CHECKS}/{check_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CHECK_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_check_by_owner(client, user_factory):
    await user_factory("self@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "self@example.com")
    created = await _create_check(client, headers, answers=VALID_ANSWERS)
    check_id = created.json()["data"]["id"]

    response = await client.get(f"{CHECKS}/{check_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == check_id
    assert len(response.json()["data"]["results"]) == 14


@pytest.mark.asyncio
async def test_list_pagination(client, user_factory):
    await user_factory("page@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "page@example.com")
    for i in range(3):
        await _create_check(client, headers, case_title=f"Проверка {i}")

    page1 = await client.get(CHECKS, params={"page": 1, "per_page": 2})
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["data"]) == 2
    assert body1["meta"] == {"page": 1, "per_page": 2, "total": 3}

    page2 = await client.get(CHECKS, params={"page": 2, "per_page": 2})
    assert len(page2.json()["data"]) == 1


@pytest.mark.asyncio
async def test_create_check_validation_error(client, user_factory):
    await user_factory("val@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "val@example.com")

    response = await client.post(
        CHECKS, json={"case_title": "без ответов"}, headers=headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
