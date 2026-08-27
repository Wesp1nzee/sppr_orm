"""Критерий 4: согласие участника записи."""

from typing import Any, ClassVar

from app.checks.constants import CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion04(CriterionRule):
    number = 4
    legal_references: ClassVar[list[str]] = ["fz-ord-art8"]

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
                    "Оценить риск оспаривания допустимости записи и "
                    "зафиксировать согласие участника."
                ],
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Согласие участника отсутствует — нарушений не выявлено.",
        )


__all__ = ["Criterion04"]
