"""Интеграционные тесты API домена «Аудит»."""

import io
import uuid
from collections.abc import Awaitable, Callable

import httpx
import pytest
from docx import Document
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.audit.models import AuditLogEntry
from app.audit.repository import AuditLogRepository
from app.auth.models import User, UserRole

UserFactory = Callable[..., Awaitable[User]]

AUDIT = "/api/v1/audit"
CHECKS = "/api/v1/checks"
DOCUMENTS = "/api/v1/documents"
LOGIN = "/api/v1/auth/login"
PASSWORD = "strong-password-123"

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
PDF_MEDIA_TYPE = "application/pdf"

EXCLUSION_EXTRA_FIELDS = {
    "addressee": "Суд",
    "applicant_name": "Иванов Иван Иванович",
    "case_number": "1-123/2026",
}


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


async def _add_entry(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    event_type: str,
    user_id: uuid.UUID | None,
    payload: dict[str, object] | None = None,
) -> uuid.UUID:
    async with session_factory() as session:
        entry = AuditLogEntry(
            event_type=event_type, user_id=user_id, payload=payload or {}
        )
        await AuditLogRepository(session).add(entry)
        await session.commit()
        return entry.id


async def _create_check(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(CHECKS, json={"answers": {}}, headers=headers)
    assert response.status_code == 201
    return str(response.json()["data"]["id"])


@pytest.mark.asyncio
async def test_anonymous_list_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{AUDIT}/logs")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [UserRole.lawyer, UserRole.investigator, UserRole.officer],
)
@pytest.mark.asyncio
async def test_non_admin_cannot_access_logs(
    client: httpx.AsyncClient, user_factory: UserFactory, role: UserRole
) -> None:
    email = f"{role.value}@example.com"
    await user_factory(email, PASSWORD, role)
    await _login(client, email)

    response = await client.get(f"{AUDIT}/logs")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_admin_can_list_logs_with_filters_and_pagination(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_a = await user_factory("a@example.com", PASSWORD, UserRole.lawyer)
    user_b = await user_factory("b@example.com", PASSWORD, UserRole.officer)
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)

    await _add_entry(session_factory, event_type="CheckCreated", user_id=user_a.id)
    await _add_entry(session_factory, event_type="UserLoggedIn", user_id=user_a.id)
    await _add_entry(session_factory, event_type="CheckCreated", user_id=user_b.id)

    await _login(client, "admin@example.com")

    response = await client.get(f"{AUDIT}/logs")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 3
    assert body["meta"] == {"page": 1, "per_page": 20, "total": 3}

    filtered = await client.get(f"{AUDIT}/logs", params={"event_type": "CheckCreated"})
    assert len(filtered.json()["data"]) == 2

    by_user = await client.get(f"{AUDIT}/logs", params={"user_id": str(user_a.id)})
    assert len(by_user.json()["data"]) == 2

    paged = await client.get(f"{AUDIT}/logs", params={"page": 2, "per_page": 2})
    assert len(paged.json()["data"]) == 1


@pytest.mark.asyncio
async def test_get_entry_by_id_and_404(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)
    entry_id = await _add_entry(
        session_factory, event_type="UserLoggedIn", user_id=None
    )

    await _login(client, "admin@example.com")

    response = await client.get(f"{AUDIT}/logs/{entry_id}")
    assert response.status_code == 200
    assert response.json()["data"]["event_type"] == "UserLoggedIn"

    missing = await client.get(f"{AUDIT}/logs/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "AUDIT_LOG_ENTRY_NOT_FOUND"


@pytest.mark.asyncio
async def test_summary_report_for_owner_and_export(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    owner = await user_factory("owner@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("stranger@example.com", PASSWORD, UserRole.lawyer)

    headers = await _login(client, "owner@example.com")
    check_id = await _create_check(client, headers)

    generated = await client.post(
        f"{DOCUMENTS}?check_id={check_id}",
        json={
            "document_type": "exclusion_motion",
            "extra_fields": EXCLUSION_EXTRA_FIELDS,
        },
        headers=headers,
    )
    assert generated.status_code == 201
    document_id = generated.json()["data"]["id"]

    await _add_entry(
        session_factory,
        event_type="CheckCreated",
        user_id=owner.id,
        payload={"check_id": check_id},
    )
    await _add_entry(
        session_factory,
        event_type="DocumentCreated",
        user_id=owner.id,
        payload={"check_id": check_id, "document_id": document_id},
    )
    await _add_entry(session_factory, event_type="UserLoggedIn", user_id=owner.id)

    summary = await client.get(f"{AUDIT}/reports/{check_id}/summary")
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert data["check"]["id"] == check_id
    assert len(data["criterion_results"]) == 14
    assert [d["id"] for d in data["documents"]] == [document_id]
    assert {e["event_type"] for e in data["audit_log"]} == {
        "CheckCreated",
        "DocumentCreated",
    }

    # Чужой пользователь не видит отчёт по чужой проверке.
    await _login(client, "stranger@example.com")
    foreign = await client.get(f"{AUDIT}/reports/{check_id}/summary")
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "CHECK_NOT_FOUND"


@pytest.mark.asyncio
async def test_summary_report_accessible_by_admin(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("owner@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)

    owner_headers = await _login(client, "owner@example.com")
    check_id = await _create_check(client, owner_headers)

    await _login(client, "admin@example.com")
    response = await client.get(f"{AUDIT}/reports/{check_id}/summary")
    assert response.status_code == 200
    assert response.json()["data"]["check"]["id"] == check_id


@pytest.mark.asyncio
async def test_export_summary_report_docx_and_pdf(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("owner@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "owner@example.com")
    check_id = await _create_check(client, headers)

    docx = await client.get(f"{AUDIT}/reports/{check_id}/export?format=docx")
    assert docx.status_code == 200
    assert docx.headers["content-type"] == DOCX_MEDIA_TYPE
    assert "audit_report_" in docx.headers["content-disposition"]
    assert docx.content.startswith(b"PK")
    doc = Document(io.BytesIO(docx.content))
    assert doc.paragraphs

    pdf = await client.get(f"{AUDIT}/reports/{check_id}/export?format=pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == PDF_MEDIA_TYPE
    assert pdf.content.startswith(b"%PDF")
