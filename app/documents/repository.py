"""Репозиторий домена «Генерация документов»: чистые запросы к БД."""

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.models import DocumentStatus, DocumentType, GeneratedDocument

_SORT_COLUMNS: dict[str, Any] = {
    "created_at": GeneratedDocument.created_at,
    "status": GeneratedDocument.status,
    "document_type": GeneratedDocument.document_type,
}


class GeneratedDocumentRepositoryProtocol(Protocol):
    """Интерфейс репозитория, используемый ``DocumentService`` (DI/тесты)."""

    async def add(self, document: GeneratedDocument) -> GeneratedDocument: ...

    async def get_by_id(self, document_id: uuid.UUID) -> GeneratedDocument | None: ...

    async def list_for_check(
        self, *, check_id: uuid.UUID, page: int, per_page: int
    ) -> list[GeneratedDocument]: ...

    async def count_for_check(self, *, check_id: uuid.UUID) -> int: ...

    async def list_for_user(
        self,
        *,
        user_id: uuid.UUID | None,
        page: int,
        per_page: int,
        sort: str | None,
        check_id: uuid.UUID | None,
        document_type: DocumentType | None,
    ) -> list[GeneratedDocument]: ...

    async def count_for_user(
        self,
        *,
        user_id: uuid.UUID | None,
        check_id: uuid.UUID | None,
        document_type: DocumentType | None,
    ) -> int: ...

    async def update_content(
        self, document: GeneratedDocument, content: dict[str, Any]
    ) -> GeneratedDocument: ...

    async def set_status(
        self, document: GeneratedDocument, status: DocumentStatus
    ) -> GeneratedDocument: ...


class GeneratedDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: GeneratedDocument) -> GeneratedDocument:
        self._session.add(document)
        await self._session.flush()
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> GeneratedDocument | None:
        return await self._session.get(GeneratedDocument, document_id)

    async def list_for_check(
        self, *, check_id: uuid.UUID, page: int, per_page: int
    ) -> list[GeneratedDocument]:
        stmt = (
            select(GeneratedDocument)
            .where(GeneratedDocument.check_id == check_id)
            .order_by(GeneratedDocument.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_check(self, *, check_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(GeneratedDocument)
            .where(GeneratedDocument.check_id == check_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

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
        stmt = select(GeneratedDocument)
        if user_id is not None:
            stmt = stmt.where(GeneratedDocument.user_id == user_id)
        if check_id is not None:
            stmt = stmt.where(GeneratedDocument.check_id == check_id)
        if document_type is not None:
            stmt = stmt.where(GeneratedDocument.document_type == document_type)
        stmt = stmt.order_by(_order_by(sort))
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_user(
        self,
        *,
        user_id: uuid.UUID | None,
        check_id: uuid.UUID | None,
        document_type: DocumentType | None,
    ) -> int:
        stmt = select(func.count()).select_from(GeneratedDocument)
        if user_id is not None:
            stmt = stmt.where(GeneratedDocument.user_id == user_id)
        if check_id is not None:
            stmt = stmt.where(GeneratedDocument.check_id == check_id)
        if document_type is not None:
            stmt = stmt.where(GeneratedDocument.document_type == document_type)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def update_content(
        self, document: GeneratedDocument, content: dict[str, Any]
    ) -> GeneratedDocument:
        document.content = content
        document.updated_at = datetime.now(UTC)
        await self._session.flush()
        return document

    async def set_status(
        self, document: GeneratedDocument, status: DocumentStatus
    ) -> GeneratedDocument:
        document.status = status
        document.updated_at = datetime.now(UTC)
        await self._session.flush()
        return document


def _order_by(sort: str | None) -> Any:
    key = sort or "-created_at"
    descending = key.startswith("-")
    column = _SORT_COLUMNS.get(
        key[1:] if descending else key, GeneratedDocument.created_at
    )
    return column.desc() if descending else column.asc()


__all__ = ["GeneratedDocumentRepository", "GeneratedDocumentRepositoryProtocol"]
