"""Репозиторий домена «База знаний»: чистые запросы к БД."""

import uuid
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_base.models import NormativeDocument, NormativeSourceType

_HIGHLIGHT_OPTIONS = (
    "StartSel=<mark>, StopSel=</mark>, MaxFragments=3, MaxWords=35, MinWords=15"
)
_SQLITE_HIGHLIGHT_RADIUS = 150


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
        self, *, code: str, admin_id: uuid.UUID | None, **fields: Any
    ) -> NormativeDocument: ...

    async def search(
        self,
        *,
        query: str | None,
        source_type: NormativeSourceType | None,
        code: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        per_page: int,
    ) -> list[NormativeDocument]: ...

    async def count_search(
        self,
        *,
        query: str | None,
        source_type: NormativeSourceType | None,
        code: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> int: ...

    async def get_highlighted_snippet(
        self, document_id: uuid.UUID, query: str
    ) -> str | None: ...


class NormativeDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def _is_postgres(self) -> bool:
        return self._session.bind.dialect.name == "postgresql"

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
        self, *, code: str, admin_id: uuid.UUID | None, **fields: Any
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
        if self._is_postgres:
            doc.search_vector = func.to_tsvector("russian", self._search_text(doc))
        self._session.add(doc)
        await self._session.flush()
        return doc

    async def search(
        self,
        *,
        query: str | None,
        source_type: NormativeSourceType | None,
        code: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        per_page: int,
    ) -> list[NormativeDocument]:
        stmt = self._search_select(query, source_type, code, date_from, date_to)
        if query:
            if self._is_postgres:
                stmt = stmt.order_by(
                    func.ts_rank(
                        NormativeDocument.search_vector,
                        func.websearch_to_tsquery("russian", query),
                    ).desc()
                )
            else:
                # SQLite: релевантность недоступна, порядок — по коду.
                stmt = stmt.order_by(NormativeDocument.code)
        else:
            stmt = stmt.order_by(NormativeDocument.code)
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_search(
        self,
        *,
        query: str | None,
        source_type: NormativeSourceType | None,
        code: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> int:
        stmt = self._search_select(query, source_type, code, date_from, date_to)
        stmt = select(func.count()).select_from(stmt.subquery())
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_highlighted_snippet(
        self, document_id: uuid.UUID, query: str
    ) -> str | None:
        if self._is_postgres:
            stmt = select(
                func.ts_headline(
                    "russian",
                    NormativeDocument.full_text,
                    func.websearch_to_tsquery("russian", query),
                    _HIGHLIGHT_OPTIONS,
                )
            ).where(NormativeDocument.id == document_id)
            result = await self._session.execute(stmt)
            return result.scalar_one_or_none()
        doc = await self._session.get(NormativeDocument, document_id)
        if doc is None:
            return None
        return _sqlite_highlight(doc.full_text, query)

    def _search_select(
        self,
        query: str | None,
        source_type: NormativeSourceType | None,
        code: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> Select[Any]:
        stmt = select(NormativeDocument).where(NormativeDocument.is_current.is_(True))
        if source_type is not None:
            stmt = stmt.where(NormativeDocument.source_type == source_type)
        if code is not None:
            stmt = stmt.where(NormativeDocument.code.ilike(f"%{code}%"))
        if date_from is not None:
            stmt = stmt.where(NormativeDocument.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(NormativeDocument.created_at <= date_to)
        if query:
            stmt = self._apply_query(stmt, query)
        return stmt

    def _apply_query(self, stmt: Select[Any], query: str) -> Select[Any]:
        if self._is_postgres:
            return stmt.where(
                NormativeDocument.search_vector.op("@@")(
                    func.websearch_to_tsquery("russian", query)
                )
            )
        # SQLite-деградация: ``ilike`` → ``lower(x) LIKE lower(y)``. Нижний
        # регистр в SQLite — только ASCII, поэтому кириллица сопоставляется
        # с учётом регистра; это ожидаемая деградация (см. ADR 0004).
        pattern = f"%{query}%"
        return stmt.where(
            or_(
                NormativeDocument.title.ilike(pattern),
                NormativeDocument.full_text.ilike(pattern),
                NormativeDocument.summary.ilike(pattern),
            )
        )

    @staticmethod
    def _search_text(doc: NormativeDocument) -> str:
        parts = [doc.title, doc.full_text, doc.summary]
        return " ".join(p for p in parts if p)


def _sqlite_highlight(full_text: str, query: str) -> str | None:
    """SQLite-деградация хайлайтинга: первое вхождение ``query`` + окно ±150.

    Это упрощённая замена ``ts_headline`` (недоступен вне PostgreSQL): не
    сегментирует по лексемам и не ранжирует фрагменты, а лишь подсвечивает
    буквальное вхождение запроса.
    """
    needle = query.strip().lower()
    if not needle:
        return None
    lowered = full_text.lower()
    idx = lowered.find(needle)
    if idx == -1:
        return None
    start = max(0, idx - _SQLITE_HIGHLIGHT_RADIUS)
    end = min(len(full_text), idx + len(query) + _SQLITE_HIGHLIGHT_RADIUS)
    return (
        full_text[start:idx]
        + "<mark>"
        + full_text[idx : idx + len(query)]
        + "</mark>"
        + full_text[idx + len(query) : end]
    )


__all__ = ["NormativeDocumentRepository", "NormativeDocumentRepositoryProtocol"]
