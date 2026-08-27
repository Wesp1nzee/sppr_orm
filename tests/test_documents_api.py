"""Интеграционные тесты API домена «Генерация документов» (ТЗ, раздел 3.4)."""

import io
from collections.abc import Awaitable, Callable

import httpx
import pytest
from docx import Document

from app.auth.models import User, UserRole

UserFactory = Callable[..., Awaitable[User]]

DOCUMENTS = "/api/v1/documents"
CHECKS = "/api/v1/checks"
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


async def _create_check(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(CHECKS, json={"answers": {}}, headers=headers)
    assert response.status_code == 201
    return str(response.json()["data"]["id"])


async def _generate(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    check_id: str,
    document_type: str,
    extra_fields: dict[str, str] | None = None,
) -> httpx.Response:
    return await client.post(
        f"{DOCUMENTS}?check_id={check_id}",
        json={"document_type": document_type, "extra_fields": extra_fields or {}},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_anonymous_generate_returns_401(
    client: httpx.AsyncClient, csrf_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{DOCUMENTS}?check_id=00000000-0000-0000-0000-000000000000",
        json={"document_type": "exclusion_motion", "extra_fields": {}},
        headers=csrf_headers,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generate_edit_finalize_export_flow(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "lawyer@example.com")
    check_id = await _create_check(client, headers)

    generated = await _generate(
        client, headers, check_id, "exclusion_motion", EXCLUSION_EXTRA_FIELDS
    )
    assert generated.status_code == 201
    document_id = generated.json()["data"]["id"]
    assert generated.json()["data"]["status"] == "draft"
    assert generated.json()["data"]["content"]["перечень_нарушений"]

    updated = await client.patch(
        f"{DOCUMENTS}/{document_id}",
        json={"content": {"адресат": "Новый суд"}},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["content"] == {"адресат": "Новый суд"}

    finalized = await client.post(
        f"{DOCUMENTS}/{document_id}/finalize", headers=headers
    )
    assert finalized.status_code == 200
    assert finalized.json()["data"]["status"] == "finalized"

    docx = await client.get(f"{DOCUMENTS}/{document_id}/export?format=docx")
    assert docx.status_code == 200
    assert docx.headers["content-type"] == DOCX_MEDIA_TYPE
    assert docx.content.startswith(b"PK")

    pdf = await client.get(f"{DOCUMENTS}/{document_id}/export?format=pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == PDF_MEDIA_TYPE
    assert pdf.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_export_docx_is_valid_document(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("owner@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "owner@example.com")
    check_id = await _create_check(client, headers)

    generated = await _generate(
        client, headers, check_id, "exclusion_motion", EXCLUSION_EXTRA_FIELDS
    )
    document_id = generated.json()["data"]["id"]

    response = await client.get(f"{DOCUMENTS}/{document_id}/export?format=docx")
    doc = Document(io.BytesIO(response.content))
    assert doc.paragraphs


@pytest.mark.asyncio
async def test_foreign_document_returns_403(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("owner@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("stranger@example.com", PASSWORD, UserRole.lawyer)

    owner_headers = await _login(client, "owner@example.com")
    check_id = await _create_check(client, owner_headers)
    generated = await _generate(
        client, owner_headers, check_id, "exclusion_motion", EXCLUSION_EXTRA_FIELDS
    )
    document_id = generated.json()["data"]["id"]

    await _login(client, "stranger@example.com")
    response = await client.get(f"{DOCUMENTS}/{document_id}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_disallowed_document_type_for_role_returns_403(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "lawyer@example.com")
    check_id = await _create_check(client, headers)

    response = await _generate(client, headers, check_id, "officer_checklist")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DOCUMENT_TYPE_NOT_ALLOWED_FOR_ROLE"


@pytest.mark.asyncio
async def test_edit_finalized_returns_409(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "lawyer@example.com")
    check_id = await _create_check(client, headers)

    generated = await _generate(
        client, headers, check_id, "exclusion_motion", EXCLUSION_EXTRA_FIELDS
    )
    document_id = generated.json()["data"]["id"]
    await client.post(f"{DOCUMENTS}/{document_id}/finalize", headers=headers)

    response = await client.patch(
        f"{DOCUMENTS}/{document_id}",
        json={"content": {"адресат": "X"}},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DOCUMENT_ALREADY_FINALIZED"


@pytest.mark.asyncio
async def test_list_history_with_filters(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "lawyer@example.com")
    check_id = await _create_check(client, headers)

    await _generate(
        client, headers, check_id, "exclusion_motion", EXCLUSION_EXTRA_FIELDS
    )
    await _generate(
        client, headers, check_id, "court_decision_copy_request", EXCLUSION_EXTRA_FIELDS
    )

    response = await client.get(DOCUMENTS)
    items = response.json()["data"]
    assert len(items) == 2

    filtered = await client.get(DOCUMENTS, params={"document_type": "exclusion_motion"})
    assert [i["document_type"] for i in filtered.json()["data"]] == ["exclusion_motion"]

    by_check = await client.get(DOCUMENTS, params={"check_id": check_id})
    assert len(by_check.json()["data"]) == 2


@pytest.mark.asyncio
async def test_admin_can_access_any_document(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("admin@example.com", PASSWORD, UserRole.admin)

    lawyer_headers = await _login(client, "lawyer@example.com")
    check_id = await _create_check(client, lawyer_headers)
    generated = await _generate(
        client, lawyer_headers, check_id, "exclusion_motion", EXCLUSION_EXTRA_FIELDS
    )
    document_id = generated.json()["data"]["id"]

    await _login(client, "admin@example.com")
    response = await client.get(f"{DOCUMENTS}/{document_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == document_id


@pytest.mark.asyncio
async def test_generate_missing_fields_returns_400(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    headers = await _login(client, "lawyer@example.com")
    check_id = await _create_check(client, headers)

    response = await _generate(client, headers, check_id, "exclusion_motion", {})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DOCUMENT_TEMPLATE_MISSING_FIELDS"


@pytest.mark.asyncio
async def test_generate_for_foreign_check_returns_404(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("owner@example.com", PASSWORD, UserRole.lawyer)
    await user_factory("stranger@example.com", PASSWORD, UserRole.lawyer)

    owner_headers = await _login(client, "owner@example.com")
    check_id = await _create_check(client, owner_headers)

    stranger_headers = await _login(client, "stranger@example.com")
    response = await _generate(
        client, stranger_headers, check_id, "exclusion_motion", EXCLUSION_EXTRA_FIELDS
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CHECK_NOT_FOUND"


@pytest.mark.asyncio
async def test_missing_document_returns_404(
    client: httpx.AsyncClient, user_factory: UserFactory
) -> None:
    await user_factory("lawyer@example.com", PASSWORD, UserRole.lawyer)
    await _login(client, "lawyer@example.com")

    response = await client.get(f"{DOCUMENTS}/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"
