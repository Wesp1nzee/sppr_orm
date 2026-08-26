"""Критерий 4: согласие участника записи."""

from __future__ import annotations

from typing import Any, ClassVar

from app.checks.constants import FZ_ORD, CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion04(CriterionRule):
    number = 4
    legal_references: ClassVar[list[str]] = [f"{FZ_ORD}, ст. 8"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        participant_consent = get_bool(answers, "participant_consent")

        if participant_consent:
            return RuleOutput(
                status=CriterionStatus.ATTENTION,
                comment=(
                    "Есть согласие участника: судебное решение может не "
                    "требоваться, но допустимость записи может оспариваться."
                ),
                recommendations=[
                    "Оценить риск оспаривания допустимости записи и зафиксировать согласие участника."
                ],
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Согласие участника отсутствует — нарушений не выявлено.",
        )


__all__ = ["Criterion04"]
