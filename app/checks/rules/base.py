"""Базовые типы правил проверки и общий интерфейс критерия."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from app.auth.models import UserRole
from app.checks.constants import CRITERION_TITLES, PRIORITY_BY_ROLE, CriterionStatus


@dataclass
class CriterionResult:
    """Итоговый результат критерия (ТЗ, раздел 10 «Формат результата»)."""

    criterion_number: int
    title: str
    status: CriterionStatus
    comment: str
    legal_references: list[str]
    recommendations: list[str]
    priority_for_role: bool


@dataclass
class RuleOutput:
    """Результат вычисления правила: статус, комментарий, рекомендации."""

    status: CriterionStatus
    comment: str
    recommendations: list[str] = field(default_factory=list)


def get_bool(answers: dict[str, Any], key: str, default: bool = False) -> bool:
    """Читает булево значение из ответов, устойчиво к строкам JSON."""
    value = answers.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "да", "y"}
    return bool(value)


def get_int(answers: dict[str, Any], key: str, default: int = 0) -> int:
    """Читает целое число из ответов, устойчиво к строкам JSON."""
    value = answers.get(key, default)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def get_str(
    answers: dict[str, Any], key: str, default: str | None = None
) -> str | None:
    """Читает строку из ответов; пустая строка трактуется как отсутствие."""
    value = answers.get(key, default)
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


class CriterionRule(ABC):
    """Интерфейс одного критерия проверки."""

    number: ClassVar[int]
    legal_references: ClassVar[list[str]] = []

    @abstractmethod
    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        """Вычисляет статус критерия по входным ответам."""

    def run(self, answers: dict[str, Any], role: UserRole) -> CriterionResult:
        """Собирает полный результат, включая приоритет для роли."""
        out = self.evaluate(answers)
        return CriterionResult(
            criterion_number=self.number,
            title=CRITERION_TITLES[self.number],
            status=out.status,
            comment=out.comment,
            legal_references=list(self.legal_references),
            recommendations=out.recommendations,
            priority_for_role=self.number in PRIORITY_BY_ROLE.get(role, frozenset()),
        )


__all__ = [
    "CriterionResult",
    "CriterionRule",
    "RuleOutput",
    "get_bool",
    "get_int",
    "get_str",
]
