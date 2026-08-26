"""Критерий 8: хранение фонограмм."""

from __future__ import annotations

from typing import Any, ClassVar

from app.checks.constants import FZ_ORD, CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool, get_int


class Criterion08(CriterionRule):
    number = 8
    legal_references: ClassVar[list[str]] = [f"{FZ_ORD}, ст. 8", f"{FZ_ORD}, ст. 12"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        criminal_case_opened = get_bool(answers, "criminal_case_opened")
        storage_months = get_int(answers, "storage_months")

        if not criminal_case_opened and storage_months > 6:
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=(
                    "Уголовное дело не возбуждено, а срок хранения фонограмм "
                    "превышает 6 месяцев."
                ),
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Сроки и основания хранения фонограмм соблюдены.",
        )


__all__ = ["Criterion08"]
