"""Репозиторий домена «База знаний»: чистые запросы к БД."""

import uuid
from typing import Any, Protocol

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_base.models import NormativeDocument, NormativeSourceType


class NormativeDocumentRepositoryProtocol(Protocol):
    """Интерфейс репозитория, используемый ``KnowledgeBaseService`` (DI/тесты)."""

    async def get_current_by_code(self, code: str) -> NormativeDocument | None: ...

    async def get_current_by_codes(
        self, codes: list[str]
    ) -> list[NormativeDocument]: ...

    async def list_current(
        self,
        *,
        source_type: NormativeSourceType | None,
        page: int,
        per_page: int,
    ) -> list[NormativeDocument]: ...

    async def count_current(
        self, *, source_type: NormativeSourceType | None
    ) -> int: ...

    async def get_history(self, code: str) -> list[NormativeDocument]: ...

    async def create_new_version(
        self, *, code: str, admin_id: uuid.UUID, **fields: Any
    ) -> NormativeDocument: ...


class NormativeDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_current_by_code(self, code: str) -> NormativeDocument | None:
        stmt = select(NormativeDocument).where(
            NormativeDocument.code == code,
            NormativeDocument.is_current.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_current_by_codes(self, codes: list[str]) -> list[NormativeDocument]:
        if not codes:
            return []
        stmt = select(NormativeDocument).where(
            NormativeDocument.code.in_(codes),
            NormativeDocument.is_current.is_(True),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_current(
        self,
        *,
        source_type: NormativeSourceType | None,
        page: int,
        per_page: int,
    ) -> list[NormativeDocument]:
        stmt = select(NormativeDocument).where(NormativeDocument.is_current.is_(True))
        if source_type is not None:
            stmt = stmt.where(NormativeDocument.source_type == source_type)
        stmt = stmt.order_by(NormativeDocument.code)
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_current(self, *, source_type: NormativeSourceType | None) -> int:
        stmt = (
            select(func.count())
            .select_from(NormativeDocument)
            .where(NormativeDocument.is_current.is_(True))
        )
        if source_type is not None:
            stmt = stmt.where(NormativeDocument.source_type == source_type)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_history(self, code: str) -> list[NormativeDocument]:
        stmt = select(NormativeDocument).where(NormativeDocument.code == code)
        stmt = stmt.order_by(NormativeDocument.version.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_new_version(
        self, *, code: str, admin_id: uuid.UUID, **fields: Any
    ) -> NormativeDocument:
        """Создаёт новую версию: предыдущие теряют ``is_current``, версия +1."""
        stmt = select(func.max(NormativeDocument.version)).where(
            NormativeDocument.code == code
        )
        result = await self._session.execute(stmt)
        new_version = int(result.scalar() or 0) + 1

        await self._session.execute(
            update(NormativeDocument)
            .where(NormativeDocument.code == code)
            .values(is_current=False)
        )

        doc = NormativeDocument(
            code=code,
            version=new_version,
            is_current=True,
            created_by=admin_id,
            **fields,
        )
        self._session.add(doc)
        await self._session.flush()
        return doc


__all__ = ["NormativeDocumentRepository", "NormativeDocumentRepositoryProtocol"]
