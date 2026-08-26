"""Критерий 13: участие защитника при ограничении свободы."""

from __future__ import annotations

from typing import Any, ClassVar

from app.checks.constants import FZ_ORD, UPK, CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool, get_str


class Criterion13(CriterionRule):
    number = 13
    legal_references: ClassVar[list[str]] = [f"{FZ_ORD}, ст. 8", UPK]

    #: ОРМ, при которых участие защитника не требуется.
    EXEMPT_ORM_TYPES: frozenset[str] = frozenset({"проверочная закупка", "досмотр"})

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        rights_restricted = get_bool(answers, "rights_restricted")
        orm_type = (get_str(answers, "orm_type") or "").lower()
        defense_attorney_provided = get_bool(answers, "defense_attorney_provided")

        if (
            rights_restricted
            and orm_type not in self.EXEMPT_ORM_TYPES
            and not defense_attorney_provided
        ):
            return RuleOutput(
                status=CriterionStatus.VIOLATION,
                comment=(
                    "При реальном ограничении свободы участие защитника "
                    "обязательно, но не было обеспечено."
                ),
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment=(
                "Участие защитника обеспечено либо ограничение свободы не имело места."
            ),
        )


__all__ = ["Criterion13"]
