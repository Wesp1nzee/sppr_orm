"""Критерий 11: осведомлённость лица о судебном решении."""

from __future__ import annotations

from typing import Any, ClassVar

from app.checks.constants import FZ_ORD, CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion11(CriterionRule):
    number = 11
    legal_references: ClassVar[list[str]] = [f"{FZ_ORD}, ст. 5", f"{FZ_ORD}, ст. 12"]

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
