"""Критерий 6: обследование жилого помещения."""

from typing import Any, ClassVar

from app.checks.constants import CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool, get_str


class Criterion06(CriterionRule):
    number = 6
    legal_references: ClassVar[list[str]] = ["fz-ord-art8", "fz-ord-art9"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        premises_type = (get_str(answers, "premises_type") or "").lower()
        residents_consent = get_bool(answers, "residents_consent")
        has_court_order = get_bool(answers, "has_court_order")
        disguises_search = get_bool(answers, "disguises_search")

        if disguises_search:
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment="Обследование помещения не должно подменять обыск.",
            )
        if premises_type == "жилое" and not residents_consent and not has_court_order:
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=(
                    "Обследование жилого помещения против воли проживающих "
                    "возможно только по судебному решению."
                ),
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Порядок обследования помещения соблюдён.",
        )


__all__ = ["Criterion06"]
