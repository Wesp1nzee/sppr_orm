"""Интеграционные тесты полнотекстового поиска на реальном PostgreSQL.

Требуют ``TEST_DATABASE_URL`` — при его отсутствии весь модуль пропускается.
Проверяют то, что не воспроизводимо на SQLite: ранжирование ``ts_rank`` и
хайлайтинг ``ts_headline``.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.knowledge_base.models import NormativeSourceType
from app.knowledge_base.repository import NormativeDocumentRepository

pytestmark = pytest.mark.skipif(
    get_settings().test_database_url is None,
    reason="требуется TEST_DATABASE_URL (реальный PostgreSQL)",
)


@pytest.mark.asyncio
async def test_fts_ranking_and_headline_on_postgres(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = NormativeDocumentRepository(session)
        await repo.create_new_version(
            code="rank-low",
            admin_id=None,
            source_type=NormativeSourceType.federal_law,
            title="Документ о жилище",
            full_text="Некоторый текст, где слово квартира встречается один раз.",
            summary=None,
        )
        await repo.create_new_version(
            code="rank-high",
            admin_id=None,
            source_type=NormativeSourceType.federal_law,
            title="Квартира и проникновение в квартиру",
            full_text="квартира квартира квартира квартира квартира",
            summary="квартира",
        )
        await session.commit()

        results = await repo.search(
            query="квартира",
            source_type=None,
            code=None,
            date_from=None,
            date_to=None,
            page=1,
            per_page=10,
        )
        assert [r.code for r in results] == ["rank-high", "rank-low"]

        snippet = await repo.get_highlighted_snippet(results[0].id, "квартира")
        assert snippet is not None
        assert "<mark>" in snippet
        assert "квартира" in snippet
