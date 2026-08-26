"""Репозиторий домена «Проверки»: чистые запросы к БД."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.checks.models import Check

_SORT_COLUMNS: dict[str, Any] = {
    "created_at": Check.created_at,
    "status": Check.status,
}


class CheckRepositoryProtocol(Protocol):
    """Интерфейс репозитория, используемый ``CheckService`` (для DI и тестов)."""

    async def add(self, check: Check) -> Check: ...

    async def get_by_id(self, check_id: uuid.UUID) -> Check | None: ...

    async def count(self, *, user_id: uuid.UUID | None = None) -> int: ...

    async def list_checks(
        self,
        *,
        user_id: uuid.UUID | None,
        page: int,
        per_page: int,
        sort: str | None,
    ) -> list[Check]: ...


class CheckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, check: Check) -> Check:
        """Добавляет проверку (результаты — через cascade) и флашит."""
        self._session.add(check)
        await self._session.flush()
        return check

    async def get_by_id(self, check_id: uuid.UUID) -> Check | None:
        return await self._session.get(Check, check_id)

    async def count(self, *, user_id: uuid.UUID | None = None) -> int:
        stmt = select(func.count()).select_from(Check)
        if user_id is not None:
            stmt = stmt.where(Check.user_id == user_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_checks(
        self,
        *,
        user_id: uuid.UUID | None,
        page: int,
        per_page: int,
        sort: str | None,
    ) -> list[Check]:
        stmt = select(Check)
        if user_id is not None:
            stmt = stmt.where(Check.user_id == user_id)
        stmt = stmt.order_by(_order_by(sort))
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


def _order_by(sort: str | None) -> Any:
    """Сортировка по ``sort`` (напр. ``-created_at``); по умолчанию новизне."""
    key = sort or "-created_at"
    descending = key.startswith("-")
    column = _SORT_COLUMNS.get(key[1:] if descending else key, Check.created_at)
    return column.desc() if descending else column.asc()


__all__ = ["CheckRepository"]
