"""Критерий 11: осведомлённость лица о судебном решении."""

from typing import Any, ClassVar

from app.checks.constants import CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion11(CriterionRule):
    number = 11
    legal_references: ClassVar[list[str]] = ["fz-ord-art5", "fz-ord-art12"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        person_informed = get_bool(answers, "person_informed")

        if person_informed:
            return RuleOutput(
                status=CriterionStatus.ATTENTION,
                comment="Лицо осведомлено о проведении ОРМ и судебном решении.",
                recommendations=[
                    "Разъяснить лицу право на обжалование судебного решения."
                ],
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Лицо не осведомлено о судебном решении — нарушений не выявлено.",
        )


__all__ = ["Criterion11"]
