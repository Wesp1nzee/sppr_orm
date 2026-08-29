"""Шаблоны документов: Jinja2-рендеринг структурированного содержимого.

``build_context`` готовит данные шаблона (результаты проверки, данные
пользователя, ручные поля), а ``render_document`` рендерит ``.j2``-шаблон
в JSON — этот словарь и есть ``GeneratedDocument.content``
"""

import json
from datetime import date
from typing import Any, cast

from jinja2 import Environment, PackageLoader

from app.auth.models import UserRole
from app.checks.constants import CriterionStatus
from app.checks.schemas import CheckOut
from app.documents.constants import DOCUMENT_TITLES, KS_RF_RULINGS, RELEVANT_CRITERIA
from app.documents.models import DocumentType

_env = Environment(
    loader=PackageLoader("app.documents", "templates"),
    autoescape=False,  # noqa: S701 шаблоны выводят JSON, а не HTML
    trim_blocks=True,
    lstrip_blocks=True,
)

ROLE_LABELS: dict[UserRole, str] = {
    UserRole.lawyer: "защитник (адвокат)",
    UserRole.investigator: "следователь",
    UserRole.officer: "оперативный сотрудник",
    UserRole.admin: "администратор системы",
}


def render_document(
    document_type: DocumentType, context: dict[str, Any]
) -> dict[str, Any]:
    """Рендерит шаблон типа ``document_type`` в словарь содержимого документа."""
    template = _env.get_template(f"{document_type.value}.j2")
    return cast(dict[str, Any], json.loads(template.render(**context)))


def build_context(
    document_type: DocumentType,
    check: CheckOut,
    full_name: str,
    role: UserRole,
    extra_fields: dict[str, str],
) -> dict[str, Any]:
    """Готовит контекст шаблона из ``CheckOut``, данных пользователя и полей запроса."""
    applicant_name = extra_fields.get("applicant_name") or full_name
    case_number = extra_fields.get("case_number", "")
    addressee = extra_fields.get("addressee", "")
    signature = full_name

    context: dict[str, Any] = {
        "addressee": addressee,
        "applicant_name": applicant_name,
        "case_number": case_number,
        "full_name": full_name,
        "role_label": ROLE_LABELS[role],
        "title": DOCUMENT_TITLES[document_type],
        "date": date.today().isoformat(),
        "signature": signature,
        "violations": _relevant_violations(check, document_type),
        "ks_rf": KS_RF_RULINGS
        if document_type is DocumentType.exclusion_motion
        else [],
        "checklist_items": (
            _checklist_items(check)
            if document_type is DocumentType.officer_checklist
            else []
        ),
        "plan_stages": (
            _plan_stages(check)
            if document_type is DocumentType.legalization_plan
            else []
        ),
    }

    if document_type in (
        DocumentType.exclusion_motion,
        DocumentType.court_decision_copy_request,
        DocumentType.data_request_complaint,
    ):
        context.update(
            {
                "applicant_data": _applicant_data(
                    applicant_name, ROLE_LABELS[role], case_number
                ),
                "case_circumstances": _case_circumstances(document_type, case_number),
                "legal_basis": _legal_basis(document_type),
                "prayer": _prayer(document_type),
            }
        )
    elif document_type is DocumentType.legalization_plan:
        context["legal_basis"] = (
            "В соответствии со ст. 89 УПК РФ и ст. 11 ФЗ «Об ОРД» результаты ОРД "
            "используются в доказывании в соответствии с уголовно-процессуальным "
            "законодательством."
        )
    return context


def _relevant_violations(
    check: CheckOut, document_type: DocumentType
) -> list[dict[str, Any]]:
    """Нарушения, релевантные типу документа (не тащить все 14 без разбора)."""
    numbers = RELEVANT_CRITERIA[document_type]
    return [
        {
            "criterion_number": result.criterion_number,
            "title": result.title,
            "comment": result.comment,
            "references": [ref.title or ref.code for ref in result.legal_references],
        }
        for result in check.results
        if result.status in (CriterionStatus.VIOLATION, CriterionStatus.ATTENTION)
        and result.criterion_number in numbers
    ]


def _checklist_items(check: CheckOut) -> list[dict[str, Any]]:
    """Пункты чек-листа следователя/оперативного сотрудника (все 14 критериев)."""
    return [
        {
            "criterion_number": result.criterion_number,
            "title": result.title,
            "status": result.status.value,
            "comment": result.comment,
            "recommendations": result.recommendations,
        }
        for result in check.results
    ]


def _plan_stages(check: CheckOut) -> list[dict[str, Any]]:
    """Этапы плана легализации, привязанные к результатам критериев 9-11."""
    by_number = {result.criterion_number: result for result in check.results}
    stage_specs = [
        (
            9,
            "Проверить наличие судебного решения и оснований ОРМ "
            "(ст. 7-8 ФЗ «Об ОРД»).",
        ),
        (10, "Истребовать копию судебного решения об ОРМ для приобщения к делу."),
        (11, "Зафиксировать осведомлённость лица о проведённых ОРМ."),
    ]
    stages = []
    for index, (number, action) in enumerate(stage_specs, start=1):
        result = by_number.get(number)
        stages.append(
            {
                "номер": index,
                "действие": action,
                "комментарий": result.comment if result is not None else "",
            }
        )
    stages.append(
        {
            "номер": len(stages) + 1,
            "действие": (
                "Ввести результаты ОРД в уголовное дело в порядке ст. 89 УПК РФ."
            ),
            "комментарий": "",
        }
    )
    return stages


def _applicant_data(applicant_name: str, role_label: str, case_number: str) -> str:
    lines = [
        f"Заявитель: {applicant_name}",
        f"Процессуальный статус: {role_label}",
    ]
    if case_number:
        lines.append(f"Номер дела: {case_number}")
    return "\n".join(lines)


def _case_circumstances(document_type: DocumentType, case_number: str) -> str:
    case_ref = f" по уголовному делу № {case_number}" if case_number else ""
    return (
        f"В рамках дела{case_ref} проведена проверка законности оперативно-"
        "розыскных мероприятий, по результатам которой выявлены нарушения "
        "требований Федерального закона «Об оперативно-розыскной деятельности» "
        "и УПК РФ."
        if document_type is DocumentType.exclusion_motion
        else (
            f"В рамках дела{case_ref} установлено отсутствие копии судебного "
            "решения об ОРМ, подлежащей приобщению к материалам дела."
            if document_type is DocumentType.court_decision_copy_request
            else (
                f"В рамках дела{case_ref} лицу отказано в истребовании сведений "
                "о полученной о нём информации, что нарушает его право, "
                "предусмотренное ч. 4 ст. 5 ФЗ «Об ОРД»."
            )
        )
    )


def _legal_basis(document_type: DocumentType) -> str:
    if document_type is DocumentType.exclusion_motion:
        return (
            "В соответствии со ст. 89 УПК РФ в процессе доказывания запрещается "
            "использование результатов ОРД, если они не отвечают требованиям, "
            "предъявляемым к доказательствам УПК РФ. Согласно ст. 11 ФЗ «Об ОРД» "
            "результаты ОРД используются в доказывании в соответствии с "
            "уголовно-процессуальным законодательством."
        )
    if document_type is DocumentType.court_decision_copy_request:
        return (
            "В соответствии со ст. 12 ФЗ «Об ОРД» судебное решение о проведении "
            "ОРМ является основанием для проверки законности мероприятий; копия "
            "решения должна находиться в материалах дела."
        )
    return (
        "В соответствии с ч. 4 ст. 5 ФЗ «Об ОРД» лицо, полагающее, что действия "
        "органов, осуществляющих ОРД, привели к нарушению его прав, вправе "
        "истребовать сведения о полученной о нём информации."
    )


def _prayer(document_type: DocumentType) -> str:
    if document_type is DocumentType.exclusion_motion:
        return (
            "На основании изложенного прошу:\n"
            "1. Признать недопустимыми доказательства, полученные с нарушением "
            "закона.\n"
            "2. Исключить их из числа доказательств по уголовному делу."
        )
    if document_type is DocumentType.court_decision_copy_request:
        return (
            "На основании изложенного прошу истребовать и приобщить к материалам "
            "дела копию судебного решения о проведении оперативно-розыскных "
            "мероприятий."
        )
    return (
        "На основании изложенного прошу признать отказ в предоставлении сведений "
        "незаконным и обязать уполномоченный орган предоставить сведения о "
        "полученной обо мне информации."
    )


__all__ = ["build_context", "render_document"]
