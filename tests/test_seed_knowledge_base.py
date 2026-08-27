"""Тест идемпотентности скрипта загрузки базы знаний."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.knowledge_base.repository import NormativeDocumentRepository
from scripts.seed_knowledge_base import (
    KS_RULING_NUMBERS,
    SEED_DOCUMENTS,
    seed_knowledge_base,
)


def test_seed_contains_all_24_rulings() -> None:
    codes = {doc["code"] for doc in SEED_DOCUMENTS}
    for number in KS_RULING_NUMBERS:
        assert number.replace("О", "O") in codes


def test_seed_codes_are_unique() -> None:
    codes = [doc["code"] for doc in SEED_DOCUMENTS]
    assert len(codes) == len(set(codes))


@pytest.mark.asyncio
async def test_seed_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await seed_knowledge_base(session)
    assert first == len(SEED_DOCUMENTS)

    async with session_factory() as session:
        second = await seed_knowledge_base(session)
        total = await NormativeDocumentRepository(session).count_current(
            source_type=None
        )
    assert second == 0
    assert total == len(SEED_DOCUMENTS)
