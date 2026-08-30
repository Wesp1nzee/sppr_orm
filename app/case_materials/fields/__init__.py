"""Пакет экстракторов полей по типам документов (по модулю на тип)."""

from app.case_materials.fields.base import (
    ExtractedField,
    FieldExtractionResult,
    FieldExtractor,
)
from app.case_materials.fields.registry import FIELD_EXTRACTORS

__all__ = [
    "FIELD_EXTRACTORS",
    "ExtractedField",
    "FieldExtractionResult",
    "FieldExtractor",
]
