"""Pydantic-схемы домена «Импорт материалов дела»."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.case_materials.constants import CaseMaterialStatus


class ExtractedFieldOut(BaseModel):
    """Извлечённое значение поля с пометкой уверенности."""

    value: Any
    confidence: str


class DetectedDocumentOut(BaseModel):
    """Один распознанный документ внутри файла (для экрана подтверждения)."""

    document_type: str
    title: str
    page: int | None = None
    fields: dict[str, ExtractedFieldOut] = Field(default_factory=dict)
    text: str


class CaseMaterialListItem(BaseModel):
    """Элемент списка загрузок (без извлечённого содержимого)."""

    id: uuid.UUID
    status: CaseMaterialStatus
    original_filename: str
    mime_type: str
    file_size_bytes: int
    created_at: datetime


class CaseMaterialUploadOut(BaseModel):
    """Ответ на загрузку: статус, обнаруженные документы и черновик ответов."""

    id: uuid.UUID
    status: CaseMaterialStatus
    original_filename: str
    mime_type: str
    file_size_bytes: int
    created_at: datetime
    detected_documents: list[DetectedDocumentOut] = Field(default_factory=list)
    suggested_check_answers: dict[str, dict[str, Any]] | None = None
    error_message: str | None = None


class CaseMaterialDetailOut(CaseMaterialUploadOut):
    """Детальное представление материала (GET по id)."""


class CaseMaterialConfirmRequest(BaseModel):
    """Тело запроса на подтверждение черновика и создание проверки."""

    case_title: str | None = Field(default=None, max_length=255)
    answers: dict[str, dict[str, Any]] = Field(description="Ответы по 14 критериям")


__all__ = [
    "CaseMaterialConfirmRequest",
    "CaseMaterialDetailOut",
    "CaseMaterialListItem",
    "CaseMaterialUploadOut",
    "DetectedDocumentOut",
    "ExtractedFieldOut",
]
