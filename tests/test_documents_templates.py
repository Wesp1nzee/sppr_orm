"""Тесты рендеринга шаблонов документов"""

import uuid
from datetime import UTC, datetime

from app.auth.models import UserRole
from app.checks.constants import CriterionStatus
from app.checks.rules.registry import evaluate_criteria
from app.checks.schemas import CheckOut, CheckSummary, CriterionResultOut
from app.documents.constants import RELEVANT_CRITERIA
from app.documents.models import DocumentType
from app.documents.templates import build_context, render_document
from app.knowledge_base.schemas import NormativeReferenceOut

EXCLUSION_MOTION_SECTIONS = (
    "адресат",
    "данные_заявителя",
    "обстоятельства_дела",
    "перечень_нарушений",
    "ссылки_на_кс_рф",
    "правовое_обоснование",
    "просительная_часть",
    "дата",
    "подпись",
)

EXTRA_FIELDS = {
    "addressee": "Суд",
    "applicant_name": "Иванов Иван Иванович",
    "case_number": "1-123/2026",
}


def _check_out(results: list[CriterionResultOut]) -> CheckOut:
    return CheckOut(
        id=uuid.uuid4(),
        status="completed",
        summary=CheckSummary(
            total=len(results),
            passed=sum(1 for r in results if r.status is CriterionStatus.PASSED),
            violations=sum(1 for r in results if r.status is CriterionStatus.VIOLATION),
            attention=sum(1 for r in results if r.status is CriterionStatus.ATTENTION),
        ),
        priority_criteria_numbers=[],
        results=results,
        case_title=None,
        created_at=datetime.now(UTC),
    )


def _default_check() -> CheckOut:
    results = [
        CriterionResultOut(
            criterion_number=r.criterion_number,
            title=r.title,
            status=r.status,
            comment=r.comment,
            legal_references=[
                NormativeReferenceOut(code=code) for code in r.legal_references
            ],
            recommendations=r.recommendations,
            priority_for_role=r.priority_for_role,
        )
        for r in evaluate_criteria(UserRole.lawyer, {})
    ]
    return _check_out(results)


def test_exclusion_motion_has_all_mandatory_sections() -> None:
    check = _default_check()
    context = build_context(
        DocumentType.exclusion_motion,
        check,
        "Иванов Иван",
        UserRole.lawyer,
        EXTRA_FIELDS,
    )
    content = render_document(DocumentType.exclusion_motion, context)

    assert set(content) == set(EXCLUSION_MOTION_SECTIONS)
    for section in EXCLUSION_MOTION_SECTIONS:
        assert content[section], f"раздел {section!r} пуст"
    assert len(content["перечень_нарушений"]) > 0
    assert len(content["ссылки_на_кс_рф"]) > 0


def test_violations_contain_only_relevant_statuses() -> None:
    results = [
        CriterionResultOut(
            criterion_number=1,
            title="Критерий 1",
            status=CriterionStatus.PASSED,
            comment="пройден",
            legal_references=[NormativeReferenceOut(code="fz-ord-art7")],
            recommendations=[],
            priority_for_role=False,
        ),
        CriterionResultOut(
            criterion_number=2,
            title="Критерий 2",
            status=CriterionStatus.VIOLATION,
            comment="нарушение",
            legal_references=[NormativeReferenceOut(code="fz-ord-art8")],
            recommendations=[],
            priority_for_role=False,
        ),
        CriterionResultOut(
            criterion_number=10,
            title="Критерий 10",
            status=CriterionStatus.ATTENTION,
            comment="нет копии решения",
            legal_references=[NormativeReferenceOut(code="fz-ord-art12")],
            recommendations=[],
            priority_for_role=False,
        ),
    ]
    check = _check_out(results)

    content = render_document(
        DocumentType.exclusion_motion,
        build_context(
            DocumentType.exclusion_motion,
            check,
            "Иванов",
            UserRole.lawyer,
            EXTRA_FIELDS,
        ),
    )
    numbers = {v["criterion_number"] for v in content["перечень_нарушений"]}
    assert numbers == {2, 10}


def test_copy_request_relevant_to_criterion_10() -> None:
    check = _default_check()
    context = build_context(
        DocumentType.court_decision_copy_request,
        check,
        "Иванов",
        UserRole.lawyer,
        EXTRA_FIELDS,
    )
    content = render_document(DocumentType.court_decision_copy_request, context)

    for violation in content["перечень_нарушений"]:
        assert (
            violation["criterion_number"]
            in RELEVANT_CRITERIA[DocumentType.court_decision_copy_request]
        )


def test_data_request_complaint_relevant_to_criterion_12() -> None:
    check = _default_check()
    context = build_context(
        DocumentType.data_request_complaint,
        check,
        "Иванов",
        UserRole.lawyer,
        EXTRA_FIELDS,
    )
    content = render_document(DocumentType.data_request_complaint, context)

    for violation in content["перечень_нарушений"]:
        assert violation["criterion_number"] == 12
