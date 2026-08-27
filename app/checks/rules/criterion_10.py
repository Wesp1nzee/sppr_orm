"""Критерий 10: копия судебного решения в материалах дела."""

from typing import Any, ClassVar

from app.checks.constants import CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion10(CriterionRule):
    number = 10
    legal_references: ClassVar[list[str]] = ["fz-ord-art12"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        has_court_order_copy = get_bool(answers, "has_court_order_copy")

        if not has_court_order_copy:
            return RuleOutput(
                status=CriterionStatus.ATTENTION,
                comment="Копия судебного решения об ОРМ отсутствует в материалах дела.",
                recommendations=["Истребовать копию судебного решения об ОРМ."],
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Копия судебного решения имеется в материалах дела.",
        )


__all__ = ["Criterion10"]
