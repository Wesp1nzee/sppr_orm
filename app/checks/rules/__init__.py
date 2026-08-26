"""Пакет правил 14 критериев проверки законности ОРМ."""

from app.checks.rules.base import CriterionResult, CriterionRule, RuleOutput
from app.checks.rules.registry import RULES, evaluate_criteria

__all__ = [
    "RULES",
    "CriterionResult",
    "CriterionRule",
    "RuleOutput",
    "evaluate_criteria",
]
