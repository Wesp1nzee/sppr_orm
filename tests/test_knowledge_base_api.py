"""Интеграционные тесты API домена «База знаний»."""

from collections.abc import Awaitable, Callable

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import User, UserRole
from app.knowledge_base.models import NormativeDocument

UserFactory = Callable[..., Awaitable[User]]

DOCUMENTS = "/api/v1/knowledge-base/documents"
LOGIN = "/api/v1/auth/login"
PASSWORD = "strong-password-123"


def _payload(code: str = "fz-ord-art8", **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "source_type": "federal_law",
        "code": code,
        "title": "ФЗ «Об ОРД», ст. 8",
        "full_text": "Условия проведения оперативно-розыскных мероприятий...",
        "summary": "Проведение ОРМ, ограничивающих конституционные права, "
        "допускается на основании судебного решения.",
        "source_url": "http://pravo.gov.ru",
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
async def test_anonymous_list_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.get(DOCUMENTS)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_create_and_get_document(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")

    created = await client.post(DOCUMENTS, json=_payload(), headers=headers)
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["code"] == "fz-ord-art8"
    assert data["version"] == 1
    assert data["is_current"] is True

    response = await client.get(f"{DOCUMENTS}/fz-ord-art8")
    assert response.status_code == 200
    assert response.json()["data"]["code"] == "fz-ord-art8"


@pytest.mark.asyncio
async def test_non_admin_can_view_documents(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)

    admin_headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload(), headers=admin_headers)

    await _login(client, "lawyer@example.com")
    response = await client.get(DOCUMENTS)
    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) == 1
    assert items[0]["code"] == "fz-ord-art8"


@pytest.mark.asyncio
async def test_non_admin_cannot_create_document(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "lawyer@example.com")

    response = await client.post(DOCUMENTS, json=_payload(), headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_non_admin_cannot_update_document(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)

    admin_headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload(), headers=admin_headers)

    lawyer_headers = await _login(client, "lawyer@example.com")
    response = await client.put(
        f"{DOCUMENTS}/fz-ord-art8", json={"title": "изменено"}, headers=lawyer_headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_update_creates_new_version_and_keeps_history(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")
    await client.post(DOCUMENTS, json=_payload(), headers=headers)

    updated = await client.put(
        f"{DOCUMENTS}/fz-ord-art8",
        json={"title": "ФЗ «Об ОРД», ст. 8 (ред. 2026)"},
        headers=headers,
    )
    assert updated.status_code == 200
    data = updated.json()["data"]
    assert data["version"] == 2
    assert data["is_current"] is True
    assert data["title"] == "ФЗ «Об ОРД», ст. 8 (ред. 2026)"

    history = await client.get(f"{DOCUMENTS}/fz-ord-art8/history")
    assert history.status_code == 200
    versions = history.json()["data"]
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[0]["is_current"] is True
    assert versions[1]["is_current"] is False

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(NormativeDocument).where(
                        NormativeDocument.code == "fz-ord-art8"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2


@pytest.mark.asyncio
async def test_get_missing_document_returns_404(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    await _login(client, "lawyer@example.com")

    response = await client.get(f"{DOCUMENTS}/no-such-code")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NORMATIVE_DOCUMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_duplicate_code_returns_409(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    headers = await _login(client, "admin@example.com")

    assert (
        await client.post(DOCUMENTS, json=_payload(), headers=headers)
    ).status_code == 201
    duplicate = await client.post(DOCUMENTS, json=_payload(), headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "NORMATIVE_DOCUMENT_CODE_CONFLICT"


@pytest.mark.asyncio
async def test_list_pagination_and_source_type_filter(
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

    response = await client.get(DOCUMENTS, params={"per_page": 1})
    body = response.json()
    assert len(body["data"]) == 1
    assert body["meta"] == {"page": 1, "per_page": 1, "total": 2}

    filtered = await client.get(DOCUMENTS, params={"source_type": "ks_rf_ruling"})
    items = filtered.json()["data"]
    assert [i["code"] for i in items] == ["ks-86-O"]
