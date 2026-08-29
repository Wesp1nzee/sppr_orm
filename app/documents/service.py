"""Бизнес-логика домена «Генерация документов»."""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.checks.service import CheckService
from app.core.events import EventBus, get_event_bus
from app.core.exceptions import AppException, ErrorCode
from app.core.pagination import PageParams
from app.documents.constants import (
    DOCUMENT_TITLES,
    DOCUMENT_TYPES_BY_ROLE,
    REQUIRED_EXTRA_FIELDS,
    TEMPLATE_VERSION,
)
from app.documents.export import export_docx, export_pdf
from app.documents.models import DocumentStatus, DocumentType, GeneratedDocument
from app.documents.repository import (
    GeneratedDocumentRepository,
    GeneratedDocumentRepositoryProtocol,
)
from app.documents.schemas import (
    DocumentContentUpdateRequest,
    GeneratedDocumentListItem,
    GeneratedDocumentOut,
)
from app.documents.templates import build_context, render_document

ExportFormat = Literal["docx", "pdf"]


@dataclass(frozen=True)
class DocumentCreated:
    """Событие: создан документ (для подписчиков, напр. ``app/audit``)."""

    document_id: uuid.UUID
    check_id: uuid.UUID
    user_id: uuid.UUID
    document_type: DocumentType


@dataclass(frozen=True)
class DocumentFinalized:
    """Событие: документ финализирован."""

    document_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class DocumentExported:
    """Событие: документ экспортирован в DOCX/PDF."""

    document_id: uuid.UUID
    user_id: uuid.UUID
    format: ExportFormat


@dataclass(frozen=True)
class DocumentContentUpdated:
    """Событие: содержимое черновика изменено."""

    document_id: uuid.UUID
    user_id: uuid.UUID


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        repo: GeneratedDocumentRepositoryProtocol | None = None,
        checks: CheckService | None = None,
        events: EventBus | None = None,
    ) -> None:
        self._session = session
        self._repo = repo or GeneratedDocumentRepository(session)
        self._checks = checks or CheckService(session)
        self._events = events or get_event_bus()

    async def generate(
        self,
        user: User,
        check_id: uuid.UUID,
        document_type: DocumentType,
        extra_fields: dict[str, str],
    ) -> GeneratedDocumentOut:
        """Генерирует документ: проверяет доступ, роль, поля; рендерит шаблон."""
        check = await self._checks.get_for_user(user, check_id)
        self._ensure_type_allowed(user.role, document_type)
        self._ensure_required_fields(document_type, extra_fields)

        context = build_context(
            document_type, check, user.full_name, user.role, extra_fields
        )
        content = render_document(document_type, context)

        document = GeneratedDocument(
            check_id=check.id,
            user_id=user.id,
            document_type=document_type,
            status=DocumentStatus.draft,
            title=DOCUMENT_TITLES[document_type],
            content=content,
            template_version=TEMPLATE_VERSION,
        )
        await self._repo.add(document)
        await self._events.publish(
            DocumentCreated(
                document_id=document.id,
                check_id=check.id,
                user_id=user.id,
                document_type=document_type,
            )
        )
        return self._to_out(document)

    async def update_content(
        self, user: User, document_id: uuid.UUID, payload: DocumentContentUpdateRequest
    ) -> GeneratedDocumentOut:
        """Редактирует содержимое черновика (только владелец, только draft)."""
        document = await self._repo.get_by_id(document_id)
        if document is None:
            raise AppException(ErrorCode.DOCUMENT_NOT_FOUND)
        if document.user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        if document.status is DocumentStatus.finalized:
            raise AppException(ErrorCode.DOCUMENT_ALREADY_FINALIZED)
        await self._repo.update_content(document, payload.content)
        await self._events.publish(
            DocumentContentUpdated(document_id=document.id, user_id=user.id)
        )
        return self._to_out(document)

    async def finalize(
        self, user: User, document_id: uuid.UUID
    ) -> GeneratedDocumentOut:
        """Финализирует черновик: фиксирует содержимое для экспорта."""
        document = await self._require_owned(user, document_id)
        if document.status is DocumentStatus.finalized:
            raise AppException(ErrorCode.DOCUMENT_ALREADY_FINALIZED)
        await self._repo.set_status(document, DocumentStatus.finalized)
        await self._events.publish(
            DocumentFinalized(document_id=document.id, user_id=user.id)
        )
        return self._to_out(document)

    async def get_for_user(
        self, user: User, document_id: uuid.UUID
    ) -> GeneratedDocumentOut:
        """Возвращает документ владельцу или администратору."""
        document = await self._require_owned(user, document_id)
        return self._to_out(document)

    async def list_for_check(
        self, user: User, check_id: uuid.UUID, page: PageParams
    ) -> tuple[list[GeneratedDocumentListItem], int]:
        """История документов по проверке (после проверки доступа к ``check_id``)."""
        await self._checks.get_for_user(user, check_id)
        documents = await self._repo.list_for_check(
            check_id=check_id, page=page.page, per_page=page.per_page
        )
        total = await self._repo.count_for_check(check_id=check_id)
        return [self._to_list_item(d) for d in documents], total

    async def list_for_user(
        self,
        user: User,
        page: PageParams,
        check_id: uuid.UUID | None = None,
        document_type: DocumentType | None = None,
    ) -> tuple[list[GeneratedDocumentListItem], int]:
        """История документов пользователя (admin видит все), с фильтрами."""
        user_id = None if user.role is UserRole.admin else user.id
        documents = await self._repo.list_for_user(
            user_id=user_id,
            page=page.page,
            per_page=page.per_page,
            sort=page.sort,
            check_id=check_id,
            document_type=document_type,
        )
        total = await self._repo.count_for_user(
            user_id=user_id, check_id=check_id, document_type=document_type
        )
        return [self._to_list_item(d) for d in documents], total

    async def export(
        self, user: User, document_id: uuid.UUID, format: ExportFormat
    ) -> bytes:
        """Экспортирует финализированный документ в DOCX/PDF (байты файла)."""
        document = await self._require_owned(user, document_id)
        if format == "docx":
            content = export_docx(document.content, document.title)
        else:
            content = export_pdf(document.content, document.title)
        await self._events.publish(
            DocumentExported(document_id=document.id, user_id=user.id, format=format)
        )
        return content

    async def _require_owned(
        self, user: User, document_id: uuid.UUID
    ) -> GeneratedDocument:
        document = await self._repo.get_by_id(document_id)
        if document is None:
            raise AppException(ErrorCode.DOCUMENT_NOT_FOUND)
        if document.user_id != user.id and user.role is not UserRole.admin:
            raise AppException(ErrorCode.FORBIDDEN)
        return document

    @staticmethod
    def _ensure_type_allowed(role: UserRole, document_type: DocumentType) -> None:
        if document_type not in DOCUMENT_TYPES_BY_ROLE[role]:
            raise AppException(ErrorCode.DOCUMENT_TYPE_NOT_ALLOWED_FOR_ROLE)

    @staticmethod
    def _ensure_required_fields(
        document_type: DocumentType, extra_fields: dict[str, str]
    ) -> None:
        missing = [
            field
            for field in REQUIRED_EXTRA_FIELDS[document_type]
            if not extra_fields.get(field)
        ]
        if missing:
            raise AppException(
                ErrorCode.DOCUMENT_TEMPLATE_MISSING_FIELDS,
                fields=", ".join(missing),
            )

    def _to_out(self, document: GeneratedDocument) -> GeneratedDocumentOut:
        return GeneratedDocumentOut.model_validate(document)

    def _to_list_item(self, document: GeneratedDocument) -> GeneratedDocumentListItem:
        return GeneratedDocumentListItem.model_validate(document)


__all__ = [
    "DocumentContentUpdated",
    "DocumentCreated",
    "DocumentExported",
    "DocumentFinalized",
    "DocumentService",
]
