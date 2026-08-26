"""Критерий 7: продление ПТП при новых оперативных данных."""

from __future__ import annotations

from typing import Any, ClassVar

from app.checks.constants import FZ_ORD, CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool, get_int


class Criterion07(CriterionRule):
    number = 7
    legal_references: ClassVar[list[str]] = [f"{FZ_ORD}, ст. 8", f"{FZ_ORD}, ст. 9"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        extensions_count = get_int(answers, "extensions_count")
        has_new_materials = get_bool(answers, "has_new_materials")

        if extensions_count > 0 and not has_new_materials:
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=("Продление ПТП без новых оперативных данных недопустимо."),
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Продление ПТП обосновано новыми оперативными данными.",
        )


__all__ = ["Criterion07"]
