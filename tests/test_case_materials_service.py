"""Тесты сервиса «Импорт материалов дела» (метод build_check_draft)."""

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import User, UserRole
from app.case_materials.constants import CaseMaterialStatus
from app.case_materials.models import CaseMaterialUpload
from app.case_materials.service import CaseMaterialService

UserFactory = Callable[..., Awaitable[User]]


@pytest.mark.asyncio
async def test_build_check_draft_splits_matched_and_unmatched(
    session_factory: async_sessionmaker[AsyncSession],
    user_factory: UserFactory,
    tmp_path: Path,
) -> None:
    user = await user_factory("draft@example.com", "password123", UserRole.lawyer)
    async with session_factory() as session:
        material = CaseMaterialUpload(
            user_id=user.id,
            original_filename="x.pdf",
            mime_type="application/pdf",
            file_size_bytes=10,
            storage_path="x",
            content_hash="h",
            status=CaseMaterialStatus.extracted,
            extracted_text="ПОСТАНОВЛЕНИЕ\nзаявление текст",
            detected_documents=[
                {
                    "document_type": "resolution_to_conduct_orm",
                    "title": "Постановление",
                    "start": 0,
                    "end": 13,
                    "fields": {},
                },
                {
                    "document_type": "consent_statement",
                    "title": "Заявление",
                    "start": 14,
                    "end": 29,
                    "fields": {},
                },
            ],
            suggested_check_answers={"criterion_13": {"orm_type": "досмотр"}},
        )
        session.add(material)
        await session.flush()

        draft = await CaseMaterialService(
            session, storage_dir=tmp_path
        ).build_check_draft(user, material.id)

    assert draft["answers"] == {"criterion_13": {"orm_type": "досмотр"}}
    assert len(draft["unmatched_documents"]) == 1
    assert draft["unmatched_documents"][0]["document_type"] == "consent_statement"
    assert "заявление текст" in draft["unmatched_documents"][0]["text"]
