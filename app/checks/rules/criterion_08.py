"""Критерий 8: хранение фонограмм."""

from typing import Any, ClassVar

from app.checks.constants import CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool, get_int


class Criterion08(CriterionRule):
    number = 8
    legal_references: ClassVar[list[str]] = ["fz-ord-art8", "fz-ord-art12"]

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
