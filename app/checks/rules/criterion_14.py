"""Критерий 14: законность задержания/удержания."""

from __future__ import annotations

from typing import Any, ClassVar

from app.checks.constants import FZ_ORD, UPK, CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool, get_str

KOAP = "КоАП РФ"


class Criterion14(CriterionRule):
    number = 14
    legal_references: ClassVar[list[str]] = [f"{FZ_ORD}, ст. 6", UPK, KOAP]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        detention_basis = get_str(answers, "detention_basis")
        has_protocol = get_bool(answers, "has_protocol")

        if detention_basis is not None and not has_protocol:
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=(
                    "Удержание/задержание произведено без протокола по "
                    "КоАП/УПК — ФЗ об ОРД не предусматривает задержание."
                ),
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Задержание оформлено надлежащим протоколом либо не производилось.",
        )


__all__ = ["Criterion14"]
