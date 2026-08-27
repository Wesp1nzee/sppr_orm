"""Pydantic-схемы домена «Проверка по 14 критериям» (ТЗ, разделы 7-8)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.checks.constants import CriterionStatus
from app.knowledge_base.schemas import NormativeReferenceOut


class CriterionResultOut(BaseModel):
    """Результат одного критерия в ответе API."""

    criterion_number: int
    title: str
    status: CriterionStatus
    comment: str
    legal_references: list[NormativeReferenceOut]
    recommendations: list[str]
    priority_for_role: bool


class CheckSummary(BaseModel):
    """Сводка по проверке: счётчики статусов."""

    total: int
    passed: int
    violations: int
    attention: int


class CheckCreateRequest(BaseModel):
    """Тело запроса на запуск проверки."""

    case_title: str | None = Field(default=None, max_length=255)
    answers: dict[str, dict[str, Any]] = Field(description="Ответы по 14 критериям")


class CheckOut(BaseModel):
    """Полное представление проверки (POST и GET по id)."""

    id: uuid.UUID
    status: str
    summary: CheckSummary
    priority_criteria_numbers: list[int]
    results: list[CriterionResultOut]
    case_title: str | None = None
    created_at: datetime


class CheckListItem(BaseModel):
    """Элемент списка проверок (без детальных результатов)."""

    id: uuid.UUID
    status: str
    summary: CheckSummary
    priority_criteria_numbers: list[int]
    case_title: str | None = None
    created_at: datetime


__all__ = [
    "CheckCreateRequest",
    "CheckListItem",
    "CheckOut",
    "CheckSummary",
    "CriterionResultOut",
]
