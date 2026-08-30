"""Базовые типы и помощники для извлечения полей из документов."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

HIGH = "high"
LOW = "low"


@dataclass
class ExtractedField:
    """Извлечённое значение с пометкой уверенности."""

    value: Any
    confidence: str

    @property
    def is_confident(self) -> bool:
        return self.confidence == HIGH


@dataclass
class FieldExtractionResult:
    """Результат экстрактора: поля + предложенные ответы для проверки."""

    fields: dict[str, ExtractedField] = field(default_factory=dict)
    suggested_answers: dict[str, dict[str, Any]] = field(default_factory=dict)


class FieldExtractor(ABC):
    """Извлекает структурные поля из текста одного типа документа."""

    @abstractmethod
    def extract(self, text: str) -> FieldExtractionResult: ...


def normalize(text: str) -> str:
    """Склеивает переносы и схлопывает пробелы в один пробел."""
    joined = re.sub(r"-\s*\n\s*", "", text)
    return re.sub(r"\s+", " ", joined).strip()


def capture_anchor(text: str, pattern: str) -> str | None:
    """Возвращает первую группу захвата совпадения или None."""
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def confident(value: Any) -> ExtractedField:
    return ExtractedField(value=value, confidence=HIGH)


def low(value: Any) -> ExtractedField:
    return ExtractedField(value=value, confidence=LOW)


__all__ = [
    "HIGH",
    "LOW",
    "ExtractedField",
    "FieldExtractionResult",
    "FieldExtractor",
    "capture_anchor",
    "confident",
    "low",
    "normalize",
]
