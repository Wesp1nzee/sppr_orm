"""Репозиторий домена «Аудит»: чистые запросы к БД."""

import uuid
from datetime import datetime
from typing import Any, Protocol, cast

from sqlalchemy import CursorResult, Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLogEntry

_SORT_COLUMNS: dict[str, Any] = {
    "created_at": AuditLogEntry.created_at,
    "event_type": AuditLogEntry.event_type,
}


class AuditLogRepositoryProtocol(Protocol):
    """Интерфейс репозитория, используемый ``AuditService`` (для DI и тестов)."""

    async def add(self, entry: AuditLogEntry) -> None: ...

    async def get_by_id(self, entry_id: uuid.UUID) -> AuditLogEntry | None: ...

    async def list_entries(
        self,
        *,
        user_id: uuid.UUID | None,
        event_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        per_page: int,
        sort: str | None,
    ) -> list[AuditLogEntry]: ...

    async def count(
        self,
        *,
        user_id: uuid.UUID | None,
        event_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> int: ...

    async def delete_older_than(self, cutoff: datetime) -> int: ...

    async def list_for_check(
        self, check_id: uuid.UUID, document_ids: list[uuid.UUID]
    ) -> list[AuditLogEntry]: ...


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AuditLogEntry) -> None:
        self._session.add(entry)
        await self._session.flush()

    async def get_by_id(self, entry_id: uuid.UUID) -> AuditLogEntry | None:
        return await self._session.get(AuditLogEntry, entry_id)

    async def list_entries(
        self,
        *,
        user_id: uuid.UUID | None,
        event_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int,
        per_page: int,
        sort: str | None,
    ) -> list[AuditLogEntry]:
        stmt = select(AuditLogEntry)
        stmt = _apply_filters(stmt, user_id, event_type, date_from, date_to)
        stmt = stmt.order_by(_order_by(sort))
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        user_id: uuid.UUID | None,
        event_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> int:
        stmt = select(func.count()).select_from(AuditLogEntry)
        stmt = _apply_filters(stmt, user_id, event_type, date_from, date_to)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Удаляет записи старше ``cutoff``; возвращает число удалённых."""
        result = await self._session.execute(
            delete(AuditLogEntry).where(AuditLogEntry.created_at < cutoff)
        )
        return int(cast(CursorResult[Any], result).rowcount or 0)

    async def list_for_check(
        self, check_id: uuid.UUID, document_ids: list[uuid.UUID]
    ) -> list[AuditLogEntry]:
        """Записи аудита, относящиеся к проверке (по ``payload.check_id``) или её
        документам (по ``payload.document_id``)."""
        conditions = [AuditLogEntry.payload["check_id"].as_string() == str(check_id)]
        if document_ids:
            conditions.append(
                AuditLogEntry.payload["document_id"]
                .as_string()
                .in_([str(d) for d in document_ids])
            )
        stmt = select(AuditLogEntry).where(or_(*conditions))
        stmt = stmt.order_by(AuditLogEntry.created_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


def _apply_filters(
    stmt: Select[Any],
    user_id: uuid.UUID | None,
    event_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> Select[Any]:
    if user_id is not None:
        stmt = stmt.where(AuditLogEntry.user_id == user_id)
    if event_type is not None:
        stmt = stmt.where(AuditLogEntry.event_type == event_type)
    if date_from is not None:
        stmt = stmt.where(AuditLogEntry.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLogEntry.created_at <= date_to)
    return stmt


def _order_by(sort: str | None) -> Any:
    """Сортировка по ``sort`` (напр. ``-created_at``); по умолчанию новизне."""
    key = sort or "-created_at"
    descending = key.startswith("-")
    column = _SORT_COLUMNS.get(key[1:] if descending else key, AuditLogEntry.created_at)
    return column.desc() if descending else column.asc()


__all__ = ["AuditLogRepository", "AuditLogRepositoryProtocol"]
