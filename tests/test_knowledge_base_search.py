"""Интеграционные тесты API поиска по базе знаний (SQLite-деградация)."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.auth.models import User, UserRole

UserFactory = Callable[..., Awaitable[User]]

DOCUMENTS = "/api/v1/knowledge-base/documents"
SEARCH = "/api/v1/knowledge-base/documents/search"
LOGIN = "/api/v1/auth/login"
PASSWORD = "strong-password-123"


def _payload(code: str = "fz-ord-art8", **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "source_type": "federal_law",
        "code": code,
        "title": "ФЗ «Об ОРД», ст. 8",
        "full_text": "Проведение оперативно-розыскных мероприятий, которые "
        "ограничивают конституционные права граждан, допускается на "
        "основании судебного решения. Проникновение в жилище возможно "
        "только по решению суда.",
        "summary": "ОРМ, ограничивающие конституционные права, — по решению суда.",
        "extra": {},
    }
    data.update(overrides)
    return data


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    csrf_resp = await client.get("/api/v1/auth/csrf-token")
    csrf_token = csrf_resp.json()["data"]["csrf_token"]
    resp = await client.post(
        LOGIN,
        json={"email": email, "password": PASSWORD},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 200
    return {"X-CSRF-Token": resp.json()["data"]["csrf_token"]}


@pytest.mark.asyncio
async def test_anonymous_search_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.get(SEARCH)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_by_keyword_matches_title_and_full_text(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload(), headers=headers)
    await client.post(
        DOCUMENTS,
        json=_payload(
            "upk-art187",
            title="УПК РФ, ст. 187",
            full_text="Порядок производства допроса и иных следственных действий.",
        ),
        headers=headers,
    )

    by_title = await client.get(SEARCH, params={"query": "ОРД"})
    assert [i["code"] for i in by_title.json()["data"]] == ["fz-ord-art8"]

    by_text = await client.get(SEARCH, params={"query": "жилище"})
    assert [i["code"] for i in by_text.json()["data"]] == ["fz-ord-art8"]


@pytest.mark.asyncio
async def test_search_does_not_match_irrelevant_docs(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload(), headers=headers)

    response = await client.get(SEARCH, params={"query": "квантовый компьютинг"})
    assert response.json()["data"] == []
    assert response.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_search_source_type_filter(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload("fz-ord-art8"), headers=headers)
    await client.post(
        DOCUMENTS,
        json=_payload(
            "ks-86-O", source_type="ks_rf_ruling", title="Определение КС № 86-О"
        ),
        headers=headers,
    )

    response = await client.get(SEARCH, params={"source_type": "ks_rf_ruling"})
    assert [i["code"] for i in response.json()["data"]] == ["ks-86-O"]


@pytest.mark.asyncio
async def test_search_code_partial_match_filter(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload("fz-ord-art8"), headers=headers)
    await client.post(
        DOCUMENTS,
        json=_payload("upk-art187", title="УПК РФ, ст. 187"),
        headers=headers,
    )

    response = await client.get(SEARCH, params={"code": "upk"})
    assert [i["code"] for i in response.json()["data"]] == ["upk-art187"]


@pytest.mark.asyncio
async def test_search_date_range_filter(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload("fz-ord-art8"), headers=headers)

    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    included = await client.get(SEARCH, params={"date_from": past})
    assert included.json()["meta"]["total"] == 1

    excluded = await client.get(SEARCH, params={"date_to": past})
    assert excluded.json()["meta"]["total"] == 0

    out_of_range = await client.get(SEARCH, params={"date_from": future})
    assert out_of_range.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_search_excludes_non_current_versions(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload("fz-ord-art8"), headers=headers)
    await client.put(
        f"{DOCUMENTS}/fz-ord-art8",
        json={"title": "ФЗ «Об ОРД», ст. 8 (ред.)"},
        headers=headers,
    )

    response = await client.get(SEARCH, params={"query": "ОРД"})
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["version"] == 2
    assert response.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_search_highlight_present_only_with_query(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload(), headers=headers)

    with_query = await client.get(SEARCH, params={"query": "жилище"})
    item = with_query.json()["data"][0]
    assert "<mark>" in item["highlight"]
    assert "жилище" in item["highlight"]

    without_query = await client.get(SEARCH, params={"source_type": "federal_law"})
    assert "highlight" not in without_query.json()["data"][0]


@pytest.mark.asyncio
async def test_search_pagination_and_total(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload("fz-ord-art8"), headers=headers)
    await client.post(
        DOCUMENTS,
        json=_payload("upk-art187", title="УПК РФ, ст. 187"),
        headers=headers,
    )

    response = await client.get(SEARCH, params={"per_page": 1})
    body = response.json()
    assert len(body["data"]) == 1
    assert body["meta"] == {"page": 1, "per_page": 1, "total": 2}

    second = await client.get(SEARCH, params={"per_page": 1, "page": 2})
    assert len(second.json()["data"]) == 1
    assert second.json()["meta"]["page"] == 2


@pytest.mark.asyncio
async def test_search_available_for_all_roles(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    for role in (
        UserRole.lawyer,
        UserRole.investigator,
        UserRole.officer,
        UserRole.admin,
    ):
        await user_factory(f"{role.value}@example.com", PASSWORD, role)

    admin_headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload(), headers=admin_headers)

    for role in (
        UserRole.lawyer,
        UserRole.investigator,
        UserRole.officer,
        UserRole.admin,
    ):
        email = f"{role.value}@example.com"
        await _login(client, email)
        response = await client.get(SEARCH, params={"query": "ОРД"})
        assert response.status_code == 200, role
