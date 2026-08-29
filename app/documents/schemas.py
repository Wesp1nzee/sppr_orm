"""Pydantic-схемы домена «Генерация документов»."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.documents.models import DocumentStatus, DocumentType


class DocumentGenerateRequest(BaseModel):
    """Тело запроса на генерацию документа по результатам проверки."""

    document_type: DocumentType
    extra_fields: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Ручные поля шаблона: адресат (суд/следователь), номер дела, "
            "ФИО заявителя и др."
        ),
    )


class DocumentContentUpdateRequest(BaseModel):
    """Тело запроса на редактирование содержимого черновика."""

    content: dict[str, Any]


class GeneratedDocumentOut(BaseModel):
    """Полное представление сгенерированного документа."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    check_id: uuid.UUID
    document_type: DocumentType
    status: DocumentStatus
    title: str
    content: dict[str, Any]
    template_version: str
    created_at: datetime
    updated_at: datetime


class GeneratedDocumentListItem(BaseModel):
    """Элемент списка документов (без полного ``content``)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    check_id: uuid.UUID
    document_type: DocumentType
    status: DocumentStatus
    title: str
    template_version: str
    created_at: datetime


__all__ = [
    "DocumentContentUpdateRequest",
    "DocumentGenerateRequest",
    "GeneratedDocumentListItem",
    "GeneratedDocumentOut",
]
