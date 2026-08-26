"""Реестр правил 14 критериев и точка запуска оценки."""

from __future__ import annotations

from typing import Any

from app.auth.models import UserRole
from app.checks.constants import TOTAL_CRITERIA
from app.checks.rules.base import CriterionResult, CriterionRule
from app.checks.rules.criterion_01 import Criterion01
from app.checks.rules.criterion_02 import Criterion02
from app.checks.rules.criterion_03 import Criterion03
from app.checks.rules.criterion_04 import Criterion04
from app.checks.rules.criterion_05 import Criterion05
from app.checks.rules.criterion_06 import Criterion06
from app.checks.rules.criterion_07 import Criterion07
from app.checks.rules.criterion_08 import Criterion08
from app.checks.rules.criterion_09 import Criterion09
from app.checks.rules.criterion_10 import Criterion10
from app.checks.rules.criterion_11 import Criterion11
from app.checks.rules.criterion_12 import Criterion12
from app.checks.rules.criterion_13 import Criterion13
from app.checks.rules.criterion_14 import Criterion14

RULES: list[CriterionRule] = [
    Criterion01(),
    Criterion02(),
    Criterion03(),
    Criterion04(),
    Criterion05(),
    Criterion06(),
    Criterion07(),
    Criterion08(),
    Criterion09(),
    Criterion10(),
    Criterion11(),
    Criterion12(),
    Criterion13(),
    Criterion14(),
]


def evaluate_criteria(
    role: UserRole, answers: dict[str, dict[str, Any]]
) -> list[CriterionResult]:
    """Оценивает все 14 критериев по входным ответам.

    ``answers`` — словарь вида ``{"criterion_1": {...}, ...}``; отсутствующие
    критерии оцениваются с дефолтными значениями полей.
    """
    results: list[CriterionResult] = []
    for rule in RULES:
        criterion_answers = answers.get(f"criterion_{rule.number}") or {}
        results.append(rule.run(criterion_answers, role))
    return results


assert len(RULES) == TOTAL_CRITERIA, "количество правил должно совпадать с ТЗ"

__all__ = ["RULES", "evaluate_criteria"]
