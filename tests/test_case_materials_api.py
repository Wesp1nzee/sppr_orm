"""Интеграционные тесты API домена «Импорт материалов дела»."""

import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.case_materials.service as case_materials_service
from app.audit.models import AuditLogEntry
from app.audit.subscribers import setup_audit_subscribers
from app.auth.models import User, UserRole
from app.core.config import get_settings
from app.core.events import EventBus

UserFactory = Callable[..., Awaitable[User]]

CASE_MATERIALS = "/api/v1/case-materials"
CHECKS = "/api/v1/checks"
LOGIN = "/api/v1/auth/login"
PASSWORD = "strong-password-123"

PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

RESOLUTION_LINES = [
    "УТВЕРЖДАЮ",
    "Начальник Иванов Иван Иванович",
    "ПОСТАНОВЛЕНИЕ",
    "о проведении оперативно-розыскного мероприятия",
    "Я, Петров Петр Петрович",
    "рассмотрев материалы рапорт",
    "руководствуясь ст. 7 Федерального закона от 12 августа 1995 г.",
    "провести оперативно-розыскное мероприятие «проверочная закупка»",
]


@pytest.fixture(autouse=True)
def _storage_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(get_settings(), "case_materials_storage_dir", str(tmp_path))


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


async def _upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    content: bytes,
    *,
    filename: str = "material.pdf",
    media_type: str = PDF_MEDIA_TYPE,
) -> httpx.Response:
    return await client.post(
        CASE_MATERIALS,
        files={"file": (filename, content, media_type)},
        headers=headers,
    )


async def _upload_resolution(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    pdf_factory: Callable[[list[str]], bytes],
) -> httpx.Response:
    return await _upload(client, headers, pdf_factory(RESOLUTION_LINES))


@pytest.mark.asyncio
async def test_anonymous_upload_returns_401(
    client: httpx.AsyncClient, csrf_headers: dict[str, str]
) -> None:
    response = await client.post(
        CASE_MATERIALS,
        files={"file": ("x.pdf", b"%PDF-fake", PDF_MEDIA_TYPE)},
        headers=csrf_headers,
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_upload_pdf_extracts_documents(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    pdf_factory: Callable[[list[str]], bytes],
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "lawyer@example.com")

    response = await _upload_resolution(client, headers, pdf_factory)

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "extracted"
    assert data["original_filename"] == "material.pdf"
    assert len(data["detected_documents"]) == 1
    document = data["detected_documents"][0]
    assert document["document_type"] == "resolution_to_conduct_orm"
    assert document["fields"]["orm_type"]["value"] == "проверочная закупка"
    assert document["fields"]["orm_type"]["confidence"] == "high"
    assert "ПОСТАНОВЛЕНИЕ" in document["text"]


@pytest.mark.asyncio
async def test_upload_docx_extracts_text(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    docx_factory: Callable[[list[str]], bytes],
) -> None:
    await user_factory("docx@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "docx@example.com")

    response = await _upload(
        client,
        headers,
        docx_factory(RESOLUTION_LINES),
        filename="material.docx",
        media_type=DOCX_MEDIA_TYPE,
    )

    assert response.status_code == 201
    assert response.json()["data"]["status"] == "extracted"
    assert (
        response.json()["data"]["detected_documents"][0]["document_type"]
        == "resolution_to_conduct_orm"
    )


@pytest.mark.asyncio
async def test_unreadable_pdf_degrades_to_text_extraction_failed(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    pdf_factory: Callable[[list[str]], bytes],
) -> None:
    await user_factory("scan@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "scan@example.com")

    response = await _upload(client, headers, pdf_factory(["коротко"]))

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "text_extraction_failed"
    assert data["error_message"]
    assert data["detected_documents"] == []


@pytest.mark.asyncio
async def test_unsupported_mime_returns_400(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("mime@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "mime@example.com")

    response = await _upload(client, headers, b"hello", media_type="text/plain")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CASE_MATERIAL_UNSUPPORTED_FORMAT"


@pytest.mark.asyncio
async def test_empty_file_returns_400(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("empty@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "empty@example.com")

    response = await _upload(client, headers, b"")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CASE_MATERIAL_UNSUPPORTED_FORMAT"


@pytest.mark.asyncio
async def test_corrupted_pdf_returns_failed_status(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("corrupt@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "corrupt@example.com")

    response = await _upload(client, headers, b"not a pdf at all")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "failed"
    assert data["error_message"]


@pytest.mark.asyncio
async def test_oversized_file_returns_400(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("big@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "big@example.com")

    oversized = b"x" * (25 * 1024 * 1024 + 1)
    response = await _upload(client, headers, oversized)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CASE_MATERIAL_FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_foreign_material_returns_404(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    pdf_factory: Callable[[list[str]], bytes],
) -> None:
    await user_factory("owner@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("stranger@example.com", PASSWORD, UserRole.lawyer)

    owner_headers = await _login(client, "owner@example.com")
    uploaded = await _upload_resolution(client, owner_headers, pdf_factory)
    upload_id = uploaded.json()["data"]["id"]

    await _login(client, "stranger@example.com")
    response = await client.get(f"{CASE_MATERIALS}/{upload_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CASE_MATERIAL_NOT_FOUND"


@pytest.mark.asyncio
async def test_admin_can_view_any_material(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    pdf_factory: Callable[[list[str]], bytes],
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)

    lawyer_headers = await _login(client, "lawyer@example.com")
    uploaded = await _upload_resolution(client, lawyer_headers, pdf_factory)
    upload_id = uploaded.json()["data"]["id"]

    await _login(client, "admin@example.com")
    response = await client.get(f"{CASE_MATERIALS}/{upload_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == upload_id


@pytest.mark.asyncio
async def test_list_only_own_materials(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    pdf_factory: Callable[[list[str]], bytes],
) -> None:
    await user_factory("a@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("b@example.com", PASSWORD, UserRole.lawyer)

    headers_a = await _login(client, "a@example.com")
    await _upload_resolution(client, headers_a, pdf_factory)

    headers_b = await _login(client, "b@example.com")
    await _upload_resolution(client, headers_b, pdf_factory)

    response = await client.get(CASE_MATERIALS)
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_confirm_creates_check_visible_via_checks_api(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    pdf_factory: Callable[[list[str]], bytes],
) -> None:
    await user_factory("confirm@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "confirm@example.com")

    uploaded = await _upload_resolution(client, headers, pdf_factory)
    upload_id = uploaded.json()["data"]["id"]

    response = await client.post(
        f"{CASE_MATERIALS}/{upload_id}/confirm",
        json={
            "case_title": "Дело №1",
            "answers": {
                "criterion_1": {"has_crime_signs": True, "has_instruction": True}
            },
        },
        headers=headers,
    )
    assert response.status_code == 201
    check_id = response.json()["data"]["id"]

    fetched = await client.get(f"{CHECKS}/{check_id}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["id"] == check_id
    assert fetched.json()["data"]["case_title"] == "Дело №1"
    assert len(fetched.json()["data"]["results"]) == 14


@pytest.mark.asyncio
async def test_confirm_unready_material_returns_409(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    pdf_factory: Callable[[list[str]], bytes],
) -> None:
    await user_factory("unready@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "unready@example.com")

    uploaded = await _upload(client, headers, pdf_factory(["коротко"]))
    upload_id = uploaded.json()["data"]["id"]

    response = await client.post(
        f"{CASE_MATERIALS}/{upload_id}/confirm",
        json={"answers": {}},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CASE_MATERIAL_NOT_READY"


@pytest.mark.asyncio
async def test_missing_material_returns_404(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("missing@example.com", PASSWORD, UserRole.lawyer)
    await _login(client, "missing@example.com")

    response = await client.get(f"{CASE_MATERIALS}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CASE_MATERIAL_NOT_FOUND"


@pytest.mark.asyncio
async def test_upload_writes_audit_event(
    client: httpx.AsyncClient,
    user_factory: UserFactory,
    pdf_factory: Callable[[list[str]], bytes],
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = EventBus()
    setup_audit_subscribers(bus)
    monkeypatch.setattr(case_materials_service, "get_event_bus", lambda: bus)

    await user_factory("audit@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "audit@example.com")

    response = await _upload_resolution(client, headers, pdf_factory)
    assert response.status_code == 201
    upload_id = response.json()["data"]["id"]

    async with session_factory() as session:
        result = await session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.event_type == "CaseMaterialUploaded"
            )
        )
        entries = list(result.scalars())

    assert len(entries) == 1
    assert entries[0].payload["upload_id"] == upload_id
