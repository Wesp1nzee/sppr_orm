"""Бизнес-логика домена «База знаний»: чтение, создание, версионирование."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import AppException, ErrorCode
from app.core.pagination import PageParams
from app.knowledge_base.models import NormativeSourceType
from app.knowledge_base.repository import (
    NormativeDocumentRepository,
    NormativeDocumentRepositoryProtocol,
)
from app.knowledge_base.schemas import (
    NormativeDocumentCreate,
    NormativeDocumentListItem,
    NormativeDocumentOut,
    NormativeDocumentUpdate,
)

logger = logging.getLogger("sppr_orm.knowledge_base")


class KnowledgeBaseService:
    def __init__(
        self,
        session: AsyncSession,
        repo: NormativeDocumentRepositoryProtocol | None = None,
    ) -> None:
        self._session = session
        self._repo = repo or NormativeDocumentRepository(session)

    async def get_by_code(self, code: str) -> NormativeDocumentOut:
        doc = await self._repo.get_current_by_code(code)
        if doc is None:
            raise AppException(ErrorCode.NORMATIVE_DOCUMENT_NOT_FOUND)
        return NormativeDocumentOut.model_validate(doc)

    async def get_by_codes_map(
        self, codes: list[str]
    ) -> dict[str, NormativeDocumentOut]:
        """Резолвит коды в документы; отсутствующие коды молча пропускаются."""
        docs = await self._repo.get_current_by_codes(codes)
        resolved = {d.code: NormativeDocumentOut.model_validate(d) for d in docs}
        missing = [code for code in codes if code not in resolved]
        if missing:
            logger.warning("Нормы не найдены в базе знаний: %s", ", ".join(missing))
        return resolved

    async def list_documents(
        self,
        *,
        source_type: NormativeSourceType | None,
        page: PageParams,
    ) -> tuple[list[NormativeDocumentListItem], int]:
        docs = await self._repo.list_current(
            source_type=source_type, page=page.page, per_page=page.per_page
        )
        total = await self._repo.count_current(source_type=source_type)
        return [NormativeDocumentListItem.model_validate(d) for d in docs], total

    async def get_history(self, code: str) -> list[NormativeDocumentOut]:
        docs = await self._repo.get_history(code)
        if not docs:
            raise AppException(ErrorCode.NORMATIVE_DOCUMENT_NOT_FOUND)
        return [NormativeDocumentOut.model_validate(d) for d in docs]

    async def create_document(
        self, admin: User, payload: NormativeDocumentCreate
    ) -> NormativeDocumentOut:
        existing = await self._repo.get_current_by_code(payload.code)
        if existing is not None:
            raise AppException(ErrorCode.NORMATIVE_DOCUMENT_CODE_CONFLICT)
        doc = await self._repo.create_new_version(
            code=payload.code,
            admin_id=admin.id,
            source_type=payload.source_type,
            title=payload.title,
            full_text=payload.full_text,
            summary=payload.summary,
            source_url=payload.source_url,
            extra=payload.extra,
        )
        return NormativeDocumentOut.model_validate(doc)

    async def update_document(
        self, admin: User, code: str, payload: NormativeDocumentUpdate
    ) -> NormativeDocumentOut:
        current = await self._repo.get_current_by_code(code)
        if current is None:
            raise AppException(ErrorCode.NORMATIVE_DOCUMENT_NOT_FOUND)

        fields = {
            "source_type": current.source_type,
            "title": current.title,
            "full_text": current.full_text,
            "summary": current.summary,
            "source_url": current.source_url,
            "extra": current.extra,
        }
        fields.update(payload.model_dump(exclude_unset=True))

        doc = await self._repo.create_new_version(
            code=code, admin_id=admin.id, **fields
        )
        return NormativeDocumentOut.model_validate(doc)


__all__ = ["KnowledgeBaseService"]
