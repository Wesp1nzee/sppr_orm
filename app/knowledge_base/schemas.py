"""Pydantic-схемы домена «База знаний» (ТЗ, раздел 3.3)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge_base.models import NormativeSourceType


class NormativeDocumentOut(BaseModel):
    """Полное представление документа (текущая или историческая версия)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: NormativeSourceType
    code: str
    title: str
    full_text: str
    summary: str | None
    source_url: str | None
    version: int
    is_current: bool
    extra: dict[str, Any]
    created_at: datetime


class NormativeDocumentListItem(BaseModel):
    """Элемент списка документов (без ``full_text`` и ``extra``)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: NormativeSourceType
    code: str
    title: str
    summary: str | None
    version: int
    is_current: bool
    created_at: datetime


class NormativeDocumentCreate(BaseModel):
    """Тело запроса на создание документа (только admin)."""

    source_type: NormativeSourceType
    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=512)
    full_text: str
    summary: str | None = None
    source_url: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class NormativeDocumentUpdate(BaseModel):
    """Тело запроса на обновление документа = создание новой версии (admin)."""

    source_type: NormativeSourceType | None = None
    title: str | None = Field(default=None, max_length=512)
    full_text: str | None = None
    summary: str | None = None
    source_url: str | None = None
    extra: dict[str, Any] | None = None


class NormativeReferenceOut(BaseModel):
    """Ссылка на норму в результатах проверки (снимок на момент проверки)."""

    code: str
    title: str | None = None
    summary: str | None = None
    source_url: str | None = None


__all__ = [
    "NormativeDocumentCreate",
    "NormativeDocumentListItem",
    "NormativeDocumentOut",
    "NormativeDocumentUpdate",
    "NormativeReferenceOut",
]
