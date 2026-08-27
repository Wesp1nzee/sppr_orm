"""Критерий 5: отсутствие признаков провокации."""

from typing import Any, ClassVar

from app.checks.constants import CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion05(CriterionRule):
    number = 5
    legal_references: ClassVar[list[str]] = ["fz-ord-art8", "plenum-vs-2009-1"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        coercion = get_bool(answers, "coercion")
        inducement = get_bool(answers, "inducement")
        series = get_bool(answers, "series_of_provocative_purchases")

        if coercion or inducement or series:
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=(
                    "Выявлены признаки провокации: склонение, побуждение или "
                    "серия провокационных закупок."
                ),
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Признаки провокации отсутствуют.",
        )


__all__ = ["Criterion05"]
