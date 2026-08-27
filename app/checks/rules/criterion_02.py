"""Критерий 2: судебное решение при ограничении конституционных прав."""

from typing import Any, ClassVar

from app.checks.constants import CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion02(CriterionRule):
    number = 2
    legal_references: ClassVar[list[str]] = ["fz-ord-art8", "fz-ord-art9"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        limits_rights = get_bool(answers, "limits_constitutional_rights")
        has_court_order = get_bool(answers, "has_court_order")
        used_48h_norm = get_bool(answers, "used_48h_norm")

        if used_48h_norm:
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=(
                    "Норма «48 часов» не заменяет судебное решение: для ОРМ, "
                    "ограничивающих конституционные права, требуется судебное "
                    "решение."
                ),
            )
        if limits_rights and not has_court_order:
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=(
                    "ОРМ ограничивает конституционные права, но судебное "
                    "решение отсутствует."
                ),
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment=(
                "Судебное решение оформлено либо ОРМ не ограничивает "
                "конституционные права."
            ),
        )


__all__ = ["Criterion02"]
