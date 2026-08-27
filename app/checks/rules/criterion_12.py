"""Критерий 12: право на истребование сведений о себе."""

from typing import Any, ClassVar

from app.checks.constants import CriterionStatus
from app.checks.rules.base import CriterionRule, RuleOutput, get_bool


class Criterion12(CriterionRule):
    number = 12
    legal_references: ClassVar[list[str]] = ["fz-ord-art5-ch4"]

    def evaluate(self, answers: dict[str, Any]) -> RuleOutput:
        guilt_not_established = get_bool(answers, "guilt_not_established")
        orm_conducted = get_bool(answers, "orm_conducted")
        rights_violated = get_bool(answers, "rights_violated")

        if guilt_not_established and orm_conducted and rights_violated:
            return RuleOutput(
                status=CriterionStatus.ATTENTION,
                comment=(
                    "Виновность не установлена, ОРМ проводились, права нарушены "
                    "— лицо вправе истребовать сведения о себе."
                ),
                recommendations=[
                    (
                        "Подготовить заявление об истребовании сведений о себе "
                        "по ч. 4 ст. 5 ФЗ об ОРД."
                    )
                ],
            )
        return RuleOutput(
            status=CriterionStatus.PASSED,
            comment="Основания для истребования сведений о себе отсутствуют.",
        )


__all__ = ["Criterion12"]
