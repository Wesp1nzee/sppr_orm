"""Критерий 3: негласные СТС в жилом помещении."""

from typing import Any, ClassVar

from app.checks.constants import CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool, get_str


class Criterion03(CriterionRule):
    number = 3
    legal_references: ClassVar[list[str]] = ["fz-ord-art8", "fz-ord-art9"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        premises_type = (get_str(answers, "premises_type") or "").lower()
        uses_covert_sts = get_bool(answers, "uses_covert_sts")
        has_residents_consent = get_bool(answers, "has_residents_consent")
        has_court_order = get_bool(answers, "has_court_order")

        if (
            uses_covert_sts
            and premises_type == "жилое"
            and not has_residents_consent
            and not has_court_order
        ):
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=(
                    "Негласные СТС в жилом помещении без согласия проживающих "
                    "требуют судебного решения."
                ),
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Условия применения негласных СТС соблюдены.",
        )


__all__ = ["Criterion03"]
