"""Критерий 5: отсутствие признаков провокации."""

from __future__ import annotations

from typing import Any, ClassVar

from app.checks.constants import FZ_ORD, PLENUM_2009, CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion05(CriterionRule):
    number = 5
    legal_references: ClassVar[list[str]] = [f"{FZ_ORD}, ст. 8", PLENUM_2009]

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
