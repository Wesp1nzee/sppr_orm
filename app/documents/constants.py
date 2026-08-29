"""Константы домена «Генерация документов»."""

from app.auth.models import UserRole
from app.documents.models import DocumentType

# Версия шаблонов  сохраняется в каждом документе
TEMPLATE_VERSION = "1.0.0"

# адвокат формирует ходатайства и жалобу, следователь и оперативный сотрудник —
# служебные документы планирования/легализации, администратор — все типы.
DOCUMENT_TYPES_BY_ROLE: dict[UserRole, frozenset[DocumentType]] = {
    UserRole.lawyer: frozenset(
        {
            DocumentType.exclusion_motion,
            DocumentType.court_decision_copy_request,
            DocumentType.data_request_complaint,
        }
    ),
    UserRole.investigator: frozenset(
        {
            DocumentType.court_decision_copy_request,
            DocumentType.officer_checklist,
            DocumentType.legalization_plan,
        }
    ),
    UserRole.officer: frozenset(
        {
            DocumentType.officer_checklist,
            DocumentType.legalization_plan,
        }
    ),
    UserRole.admin: frozenset(DocumentType),
}

DOCUMENT_TITLES: dict[DocumentType, str] = {
    DocumentType.exclusion_motion: "Ходатайство об исключении доказательств",
    DocumentType.court_decision_copy_request: (
        "Ходатайство об истребовании копии судебного решения об ОРМ"
    ),
    DocumentType.data_request_complaint: (
        "Жалоба на отказ в истребовании сведений о себе"
    ),
    DocumentType.officer_checklist: ("Чек-лист следователя/оперативного сотрудника"),
    DocumentType.legalization_plan: "План процессуальной легализации результатов ОРМ",
}

REQUIRED_EXTRA_FIELDS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.exclusion_motion: ("addressee", "applicant_name", "case_number"),
    DocumentType.court_decision_copy_request: (
        "addressee",
        "applicant_name",
        "case_number",
    ),
    DocumentType.data_request_complaint: ("addressee", "applicant_name"),
    DocumentType.officer_checklist: (),
    DocumentType.legalization_plan: (),
}

RELEVANT_CRITERIA: dict[DocumentType, frozenset[int]] = {
    DocumentType.exclusion_motion: frozenset(range(1, 15)),
    DocumentType.court_decision_copy_request: frozenset({10}),
    DocumentType.data_request_complaint: frozenset({12}),
    DocumentType.officer_checklist: frozenset(range(1, 15)),
    DocumentType.legalization_plan: frozenset({9, 10, 11}),
}

KS_RF_RULINGS: list[dict[str, str]] = [
    {
        "number": "86-О",
        "title": "Определение Конституционного Суда РФ № 86-О",
        "summary": (
            "О недопустимости использования в доказывании результатов ОРД, "
            "полученных с нарушением закона."
        ),
    },
    {
        "number": "528-О-О",
        "title": "Определение Конституционного Суда РФ № 528-О-О",
        "summary": (
            "О судебной проверке законности ОРМ, ограничивающих конституционные "
            "права граждан."
        ),
    },
    {
        "number": "568-О",
        "title": "Определение Конституционного Суда РФ № 568-О",
        "summary": (
            "О необходимости судебного решения для ОРМ, ограничивающих права граждан."
        ),
    },
    {
        "number": "268-О",
        "title": "Определение Конституционного Суда РФ № 268-О",
        "summary": (
            "Об обязанности органов расследования соблюдать требования УПК РФ "
            "при введении результатов ОРД в уголовный процесс."
        ),
    },
]

__all__ = [
    "DOCUMENT_TITLES",
    "DOCUMENT_TYPES_BY_ROLE",
    "KS_RF_RULINGS",
    "RELEVANT_CRITERIA",
    "REQUIRED_EXTRA_FIELDS",
    "TEMPLATE_VERSION",
]
