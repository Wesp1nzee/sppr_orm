"""Модели данных домена «Импорт материалов дела»."""

import uuid
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.case_materials.constants import CaseMaterialStatus
from app.db.base import JSONB, Base


class CaseMaterialUpload(Base):
    """Загруженный файл материалов дела и результат его извлечения.

    Файл хранится на диске (``storage_path`` — имя внутри директории
    ``settings.case_materials_storage_dir``); в БД — только метаданные,
    извлечённый текст и структурный результат (``detected_documents``,
    ``suggested_check_answers``). Принадлежит пользователю (``CASCADE``).
    """

    __tablename__ = "case_material_uploads"
    __table_args__ = (Index("ix_case_material_uploads_created_at", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[CaseMaterialStatus] = mapped_column(
        SAEnum(CaseMaterialStatus, name="case_material_status", native_enum=True),
        nullable=False,
        index=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_documents: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    suggested_check_answers: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CaseMaterialUpload {self.id} ({self.status.value})>"


__all__ = ["CaseMaterialUpload"]
