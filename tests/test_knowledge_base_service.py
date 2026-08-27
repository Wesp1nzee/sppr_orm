"""Unit-тесты KnowledgeBaseService: резолвинг кодов и версионирование."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import User, UserRole
from app.core.exceptions import AppException
from app.knowledge_base.models import NormativeDocument, NormativeSourceType
from app.knowledge_base.repository import NormativeDocumentRepository
from app.knowledge_base.schemas import NormativeDocumentUpdate
from app.knowledge_base.service import KnowledgeBaseService


class FakeNormativeDocumentRepository:
    """In-memory реализация ``NormativeDocumentRepositoryProtocol``."""

    def __init__(self, documents: list[NormativeDocument] | None = None) -> None:
        self._docs: dict[str, list[NormativeDocument]] = {}
        for doc in documents or []:
            self._docs.setdefault(doc.code, []).append(doc)

    def _current(self, code: str) -> NormativeDocument | None:
        return next((d for d in self._docs.get(code, []) if d.is_current), None)

    async def get_current_by_code(self, code: str) -> NormativeDocument | None:
        return self._current(code)

    async def get_current_by_codes(self, codes: list[str]) -> list[NormativeDocument]:
        return [d for c in codes if (d := self._current(c)) is not None]

    async def list_current(
        self, *, source_type: Any, page: int, per_page: int
    ) -> list[NormativeDocument]:
        del page, per_page
        return [
            d
            for d in self._current_docs()
            if source_type is None or d.source_type is source_type
        ]

    async def count_current(self, *, source_type: Any) -> int:
        return len(
            [
                d
                for d in self._current_docs()
                if source_type is None or d.source_type is source_type
            ]
        )

    async def get_history(self, code: str) -> list[NormativeDocument]:
        return sorted(self._docs.get(code, []), key=lambda d: d.version, reverse=True)

    async def create_new_version(
        self, *, code: str, admin_id: uuid.UUID, **fields: Any
    ) -> NormativeDocument:
        del admin_id
        history = self._docs.setdefault(code, [])
        for d in history:
            d.is_current = False
        new_version = max((d.version for d in history), default=0) + 1
        doc = NormativeDocument(
            code=code, version=new_version, is_current=True, **fields
        )
        history.append(doc)
        return doc

    def _current_docs(self) -> list[NormativeDocument]:
        return [d for docs in self._docs.values() for d in docs if d.is_current]


def _make_doc(code: str, title: str = "t", summary: str = "s") -> NormativeDocument:
    return NormativeDocument(
        id=uuid.uuid4(),
        code=code,
        title=title,
        full_text="text",
        summary=summary,
        source_type=NormativeSourceType.federal_law,
        version=1,
        is_current=True,
        extra={},
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_get_by_codes_map_skips_missing_codes() -> None:
    service = KnowledgeBaseService(
        session=None,  # type: ignore[arg-type]
        repo=FakeNormativeDocumentRepository([_make_doc("fz-ord-art8")]),
    )

    resolved = await service.get_by_codes_map(["fz-ord-art8", "missing-code"])

    assert set(resolved) == {"fz-ord-art8"}
    assert resolved["fz-ord-art8"].code == "fz-ord-art8"


@pytest.mark.asyncio
async def test_get_by_codes_map_empty_input() -> None:
    service = KnowledgeBaseService(
        session=None,  # type: ignore[arg-type]
        repo=FakeNormativeDocumentRepository(),
    )
    assert await service.get_by_codes_map([]) == {}


@pytest.mark.asyncio
async def test_get_by_code_missing_raises() -> None:
    service = KnowledgeBaseService(
        session=None,  # type: ignore[arg-type]
        repo=FakeNormativeDocumentRepository(),
    )
    with pytest.raises(AppException) as exc_info:
        await service.get_by_code("missing")
    assert exc_info.value.code.value == "NORMATIVE_DOCUMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_document_creates_new_version(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = User(
        email="admin@example.com",
        hashed_password="x",
        full_name="Админ",
        role=UserRole.admin,
    )
    admin.id = uuid.uuid4()

    async with session_factory() as session:
        repo = NormativeDocumentRepository(session)
        await repo.create_new_version(
            code="fz-ord-art8",
            admin_id=admin.id,
            source_type=NormativeSourceType.federal_law,
            title="v1",
            full_text="text",
        )
        await session.commit()

        service = KnowledgeBaseService(session, repo)
        updated = await service.update_document(
            admin, "fz-ord-art8", NormativeDocumentUpdate(title="v2")
        )
        await session.commit()

    assert updated.version == 2
    assert updated.is_current is True

    async with session_factory() as session:
        history = await NormativeDocumentRepository(session).get_history("fz-ord-art8")
    assert [d.version for d in history] == [2, 1]
    assert history[0].is_current is True
    assert history[1].is_current is False
