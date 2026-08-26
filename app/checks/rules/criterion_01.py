"""Критерий 1: наличие признаков преступления и поручения следователя/дознавателя."""

from __future__ import annotations

from typing import Any, ClassVar

from app.checks.constants import FZ_ORD, CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion01(CriterionRule):
    number = 1
    legal_references: ClassVar[list[str]] = [f"{FZ_ORD}, ст. 7", f"{FZ_ORD}, ст. 8"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        has_crime_signs = get_bool(answers, "has_crime_signs")
        has_instruction = get_bool(answers, "has_instruction")

        if not has_crime_signs or not has_instruction:
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=(
                    "Отсутствуют признаки преступления либо поручение "
                    "следователя/дознавателя — основания для проведения ОРМ "
                    "не подтверждены."
                ),
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Признаки преступления и поручение следователя/дознавателя подтверждены.",
        )


__all__ = ["Criterion01"]
