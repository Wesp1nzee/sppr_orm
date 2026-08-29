"""Unit-тесты DocumentService с подставленным (in-memory) репозиторием."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.auth.models import User, UserRole
from app.checks.models import Check
from app.checks.schemas import CheckCreateRequest
from app.checks.service import CheckService
from app.core.events import EventBus
from app.core.exceptions import AppException
from app.core.pagination import PageParams
from app.documents.models import DocumentStatus, DocumentType, GeneratedDocument
from app.documents.repository import GeneratedDocumentRepositoryProtocol
from app.documents.schemas import DocumentContentUpdateRequest
from app.documents.service import (
    DocumentContentUpdated,
    DocumentExported,
    DocumentFinalized,
    DocumentService,
)
from app.knowledge_base.models import NormativeDocument
from app.knowledge_base.service import KnowledgeBaseService

PASSWORD = "x"


class FakeCheckRepository:
    def __init__(self) -> None:
        self._checks: dict[uuid.UUID, Check] = {}

    async def add(self, check: Check) -> Check:
        check.id = uuid.uuid4()
        check.created_at = datetime.now(UTC)
        self._checks[check.id] = check
        return check

    async def get_by_id(self, check_id: uuid.UUID) -> Check | None:
        return self._checks.get(check_id)

    async def count(self, *, user_id: uuid.UUID | None = None) -> int:
        del user_id
        return len(self._checks)

    async def list_checks(
        self,
        *,
        user_id: uuid.UUID | None,
        page: int,
        per_page: int,
        sort: str | None,
    ) -> list[Check]:
        del user_id, page, per_page, sort
        return list(self._checks.values())


class FakeNormativeDocumentRepository:
    async def get_current_by_code(self, code: str) -> NormativeDocument | None:
        del code
        return None

    async def get_current_by_codes(self, codes: list[str]) -> list[NormativeDocument]:
        del codes
        return []

    async def list_current(
        self, *, source_type: Any, page: int, per_page: int
    ) -> list[NormativeDocument]:
        del source_type, page, per_page
        return []

    async def count_current(self, *, source_type: Any) -> int:
        del source_type
        return 0

    async def get_history(self, code: str) -> list[NormativeDocument]:
        del code
        return []

    async def create_new_version(
        self, *, code: str, admin_id: uuid.UUID | None, **fields: Any
    ) -> NormativeDocument:
        raise NotImplementedError


class FakeGeneratedDocumentRepository(GeneratedDocumentRepositoryProtocol):
    def __init__(self) -> None:
        self._documents: dict[uuid.UUID, GeneratedDocument] = {}

    async def add(self, document: GeneratedDocument) -> GeneratedDocument:
        document.id = uuid.uuid4()
        document.created_at = datetime.now(UTC)
        document.updated_at = datetime.now(UTC)
        self._documents[document.id] = document
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> GeneratedDocument | None:
        return self._documents.get(document_id)

    async def list_for_check(
        self, *, check_id: uuid.UUID, page: int, per_page: int
    ) -> list[GeneratedDocument]:
        del page, per_page
        return [d for d in self._documents.values() if d.check_id == check_id]

    async def count_for_check(self, *, check_id: uuid.UUID) -> int:
        return sum(1 for d in self._documents.values() if d.check_id == check_id)

    async def list_for_user(
        self,
        *,
        user_id: uuid.UUID | None,
        page: int,
        per_page: int,
        sort: str | None,
        check_id: uuid.UUID | None,
        document_type: DocumentType | None,
    ) -> list[GeneratedDocument]:
        del page, per_page, sort
        docs = list(self._documents.values())
        if user_id is not None:
            docs = [d for d in docs if d.user_id == user_id]
        if check_id is not None:
            docs = [d for d in docs if d.check_id == check_id]
        if document_type is not None:
            docs = [d for d in docs if d.document_type is document_type]
        return docs

    async def count_for_user(
        self,
        *,
        user_id: uuid.UUID | None,
        check_id: uuid.UUID | None,
        document_type: DocumentType | None,
    ) -> int:
        docs = await self.list_for_user(
            user_id=user_id,
            page=1,
            per_page=1,
            sort=None,
            check_id=check_id,
            document_type=document_type,
        )
        return len(docs)

    async def update_content(
        self, document: GeneratedDocument, content: dict[str, Any]
    ) -> GeneratedDocument:
        document.content = content
        return document

    async def set_status(
        self, document: GeneratedDocument, status: DocumentStatus
    ) -> GeneratedDocument:
        document.status = status
        return document


def _make_user(role: UserRole) -> User:
    user = User(
        email="x@example.com", hashed_password=PASSWORD, full_name="Иванов", role=role
    )
    user.id = uuid.uuid4()
    return user


def _make_checks() -> tuple[CheckService, FakeCheckRepository]:
    check_repo = FakeCheckRepository()
    checks = CheckService(
        session=None,  # type: ignore[arg-type]
        repo=check_repo,
        kb=KnowledgeBaseService(
            session=None,  # type: ignore[arg-type]
            repo=FakeNormativeDocumentRepository(),
        ),
    )
    return checks, check_repo


def _make_service() -> tuple[
    DocumentService, FakeGeneratedDocumentRepository, CheckService
]:
    checks, _ = _make_checks()
    doc_repo = FakeGeneratedDocumentRepository()
    service = DocumentService(
        session=None,  # type: ignore[arg-type]
        repo=doc_repo,
        checks=checks,
    )
    return service, doc_repo, checks


async def _create_check(checks: CheckService, user: User) -> uuid.UUID:
    check = await checks.create(user, CheckCreateRequest(answers={}))
    return check.id


class RecordingEventBus(EventBus):
    """Фиксирует опубликованные события для проверки публикации доменных событий."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[Any] = []

    async def publish(self, event: Any) -> None:
        self.events.append(event)


def _make_service_with_events(
    events: RecordingEventBus,
) -> tuple[DocumentService, FakeGeneratedDocumentRepository, CheckService]:
    checks, _ = _make_checks()
    doc_repo = FakeGeneratedDocumentRepository()
    service = DocumentService(
        session=None,  # type: ignore[arg-type]
        repo=doc_repo,
        checks=checks,
        events=events,
    )
    return service, doc_repo, checks


@pytest.mark.asyncio
async def test_generate_and_edit_flow() -> None:
    user = _make_user(UserRole.lawyer)
    service, _, checks = _make_service()
    check_id = await _create_check(checks, user)

    document = await service.generate(
        user,
        check_id,
        DocumentType.exclusion_motion,
        {"addressee": "Суд", "applicant_name": "Иванов", "case_number": "1-1"},
    )
    assert document.status is DocumentStatus.draft
    assert document.content["перечень_нарушений"]

    updated = await service.update_content(
        user,
        document.id,
        DocumentContentUpdateRequest(content={"адресат": "Новый суд"}),
    )
    assert updated.content == {"адресат": "Новый суд"}

    finalized = await service.finalize(user, document.id)
    assert finalized.status is DocumentStatus.finalized

    with pytest.raises(AppException) as exc_info:
        await service.update_content(
            user,
            document.id,
            DocumentContentUpdateRequest(content={"адресат": "Ещё раз"}),
        )
    assert exc_info.value.code.value == "DOCUMENT_ALREADY_FINALIZED"


@pytest.mark.asyncio
async def test_generate_rejects_type_not_allowed_for_role() -> None:
    user = _make_user(UserRole.lawyer)
    service, _, checks = _make_service()
    check_id = await _create_check(checks, user)

    with pytest.raises(AppException) as exc_info:
        await service.generate(user, check_id, DocumentType.officer_checklist, {})
    assert exc_info.value.code.value == "DOCUMENT_TYPE_NOT_ALLOWED_FOR_ROLE"


@pytest.mark.asyncio
async def test_generate_rejects_missing_required_fields() -> None:
    user = _make_user(UserRole.lawyer)
    service, _, checks = _make_service()
    check_id = await _create_check(checks, user)

    with pytest.raises(AppException) as exc_info:
        await service.generate(user, check_id, DocumentType.exclusion_motion, {})
    assert exc_info.value.code.value == "DOCUMENT_TEMPLATE_MISSING_FIELDS"


@pytest.mark.asyncio
async def test_update_by_non_owner_returns_forbidden() -> None:
    owner = _make_user(UserRole.lawyer)
    stranger = _make_user(UserRole.lawyer)
    service, _, checks = _make_service()
    check_id = await _create_check(checks, owner)

    document = await service.generate(
        owner,
        check_id,
        DocumentType.exclusion_motion,
        {"addressee": "Суд", "applicant_name": "Иванов", "case_number": "1"},
    )

    with pytest.raises(AppException) as exc_info:
        await service.update_content(
            stranger,
            document.id,
            DocumentContentUpdateRequest(content={"адресат": "X"}),
        )
    assert exc_info.value.code.value == "FORBIDDEN"


@pytest.mark.asyncio
async def test_export_returns_valid_docx_and_pdf() -> None:
    user = _make_user(UserRole.lawyer)
    service, _, checks = _make_service()
    check_id = await _create_check(checks, user)

    document = await service.generate(
        user,
        check_id,
        DocumentType.exclusion_motion,
        {"addressee": "Суд", "applicant_name": "Иванов", "case_number": "1"},
    )

    docx = await service.export(user, document.id, "docx")
    assert docx.startswith(b"PK")

    pdf = await service.export(user, document.id, "pdf")
    assert pdf.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_list_for_check_and_user() -> None:
    user = _make_user(UserRole.lawyer)
    service, _, checks = _make_service()
    check_id = await _create_check(checks, user)

    await service.generate(
        user,
        check_id,
        DocumentType.exclusion_motion,
        {"addressee": "Суд", "applicant_name": "Иванов", "case_number": "1"},
    )
    await service.generate(
        user,
        check_id,
        DocumentType.data_request_complaint,
        {"addressee": "Суд", "applicant_name": "Иванов"},
    )

    by_check, total_by_check = await service.list_for_check(
        user, check_id, PageParams()
    )
    assert total_by_check == 2
    assert len(by_check) == 2

    by_user, total_by_user = await service.list_for_user(user, PageParams())
    assert total_by_user == 2
    assert len(by_user) == 2

    filtered, total_filtered = await service.list_for_user(
        user, PageParams(), document_type=DocumentType.exclusion_motion
    )
    assert total_filtered == 1
    assert filtered[0].document_type is DocumentType.exclusion_motion


@pytest.mark.asyncio
async def test_update_content_publishes_document_content_updated() -> None:
    user = _make_user(UserRole.lawyer)
    events = RecordingEventBus()
    service, _, checks = _make_service_with_events(events)
    check_id = await _create_check(checks, user)

    document = await service.generate(
        user,
        check_id,
        DocumentType.exclusion_motion,
        {"addressee": "Суд", "applicant_name": "Иванов", "case_number": "1"},
    )
    events.events.clear()

    await service.update_content(
        user, document.id, DocumentContentUpdateRequest(content={"адресат": "X"})
    )
    assert events.events and isinstance(events.events[-1], DocumentContentUpdated)
    assert events.events[-1].document_id == document.id


@pytest.mark.asyncio
async def test_finalize_publishes_document_finalized() -> None:
    user = _make_user(UserRole.lawyer)
    events = RecordingEventBus()
    service, _, checks = _make_service_with_events(events)
    check_id = await _create_check(checks, user)

    document = await service.generate(
        user,
        check_id,
        DocumentType.exclusion_motion,
        {"addressee": "Суд", "applicant_name": "Иванов", "case_number": "1"},
    )
    events.events.clear()

    await service.finalize(user, document.id)
    assert events.events and isinstance(events.events[-1], DocumentFinalized)
    assert events.events[-1].document_id == document.id


@pytest.mark.asyncio
async def test_export_publishes_document_exported() -> None:
    user = _make_user(UserRole.lawyer)
    events = RecordingEventBus()
    service, _, checks = _make_service_with_events(events)
    check_id = await _create_check(checks, user)

    document = await service.generate(
        user,
        check_id,
        DocumentType.exclusion_motion,
        {"addressee": "Суд", "applicant_name": "Иванов", "case_number": "1"},
    )
    events.events.clear()

    await service.export(user, document.id, "pdf")
    assert events.events and isinstance(events.events[-1], DocumentExported)
    assert events.events[-1].document_id == document.id
    assert events.events[-1].format == "pdf"
