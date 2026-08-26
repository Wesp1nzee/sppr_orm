"""Общие envelope-схемы ответов из api.md (раздел 1.2).

Успех:  {"data": {...}, "meta": {...}}   (meta — только для пагинированных)
Ошибка: {"error": {"code", "message", "details": [{"field", "issue"}]}}
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    page: int = 1
    per_page: int = 20
    total: int = 0


class DataResponse(BaseModel, Generic[T]):
    """Envelope успешного ответа.

    ``meta=None`` опускается из JSON (см. ``app/api/routing.ApiRouter``:
    ``response_model_exclude_none=True``).
    """

    data: T
    meta: PageMeta | None = None


class ErrorDetail(BaseModel):
    field: str | None = None
    issue: str = ""


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody
