"""Критерий 9: легализация результатов ОРМ."""

from __future__ import annotations

from typing import Any, ClassVar

from app.checks.constants import FZ_ORD, UPK, CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion09(CriterionRule):
    number = 9
    legal_references: ClassVar[list[str]] = [f"{FZ_ORD}, ст. 11", f"{UPK}, ст. 89"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        has_legalization = get_bool(answers, "has_legalization")
        investigative_actions_done = get_bool(answers, "investigative_actions_done")

        if has_legalization:
            return RuleOutput(
                status=CriterionStatus.PASSED,
                comment="Результаты ОРМ процессуально легализованы.",
            )
        if investigative_actions_done:
            return RuleOutput(
                status=CriterionStatus.ATTENTION,
                comment=(
                    "Следственные действия проведены, но легализация не "
                    "завершена — есть риск оспаривания допустимости."
                ),
                recommendations=[
                    "Завершить процессуальную легализацию результатов ОРМ."
                ],
            )
        return RuleOutput(
            status=CriterionStatus.VIOLATION,
            comment="Результаты ОРМ используются без процессуальной легализации.",
        )


__all__ = ["Criterion09"]
