"""Репозиторий домена «Импорт материалов дела»: чистые запросы к БД."""

import uuid
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.case_materials.models import CaseMaterialUpload

_SORT_COLUMNS: dict[str, Any] = {
    "created_at": CaseMaterialUpload.created_at,
    "status": CaseMaterialUpload.status,
}


class CaseMaterialRepositoryProtocol(Protocol):
    """Интерфейс репозитория, используемый ``CaseMaterialService`` (DI/тесты)."""

    async def add(self, material: CaseMaterialUpload) -> CaseMaterialUpload: ...

    async def get_by_id(self, upload_id: uuid.UUID) -> CaseMaterialUpload | None: ...

    async def count(self, *, user_id: uuid.UUID | None = None) -> int: ...

    async def list_for_user(
        self,
        *,
        user_id: uuid.UUID | None,
        page: int,
        per_page: int,
        sort: str | None,
    ) -> list[CaseMaterialUpload]: ...


class CaseMaterialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, material: CaseMaterialUpload) -> CaseMaterialUpload:
        self._session.add(material)
        await self._session.flush()
        return material

    async def get_by_id(self, upload_id: uuid.UUID) -> CaseMaterialUpload | None:
        return await self._session.get(CaseMaterialUpload, upload_id)

    async def count(self, *, user_id: uuid.UUID | None = None) -> int:
        stmt = select(func.count()).select_from(CaseMaterialUpload)
        if user_id is not None:
            stmt = stmt.where(CaseMaterialUpload.user_id == user_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_for_user(
        self,
        *,
        user_id: uuid.UUID | None,
        page: int,
        per_page: int,
        sort: str | None,
    ) -> list[CaseMaterialUpload]:
        stmt = select(CaseMaterialUpload)
        if user_id is not None:
            stmt = stmt.where(CaseMaterialUpload.user_id == user_id)
        stmt = stmt.order_by(_order_by(sort))
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


def _order_by(sort: str | None) -> Any:
    key = sort or "-created_at"
    descending = key.startswith("-")
    column = _SORT_COLUMNS.get(
        key[1:] if descending else key, CaseMaterialUpload.created_at
    )
    return column.desc() if descending else column.asc()


__all__ = ["CaseMaterialRepository", "CaseMaterialRepositoryProtocol"]
