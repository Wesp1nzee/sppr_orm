"""Unit-тесты правил 14 критериев проверки законности ОРМ."""

from __future__ import annotations

import time
from typing import Any

from app.auth.models import UserRole
from app.checks.constants import PRIORITY_BY_ROLE, TOTAL_CRITERIA, CriterionStatus
from app.checks.rules.base import CriterionResult
from app.checks.rules.registry import RULES, evaluate_criteria


def evaluate(
    number: int, answers: dict[str, Any], role: UserRole = UserRole.lawyer
) -> CriterionResult:
    rule = next(r for r in RULES if r.number == number)
    return rule.run(answers, role)


def test_all_fourteen_rules_registered() -> None:
    assert len(RULES) == TOTAL_CRITERIA
    assert sorted(r.number for r in RULES) == list(range(1, TOTAL_CRITERIA + 1))


def test_criterion_01_violation_without_basis() -> None:
    assert (
        evaluate(1, {"has_crime_signs": False, "has_instruction": True}).status
        is CriterionStatus.VIOLATION
    )
    assert (
        evaluate(1, {"has_crime_signs": True, "has_instruction": False}).status
        is CriterionStatus.VIOLATION
    )


def test_criterion_01_passed() -> None:
    assert (
        evaluate(1, {"has_crime_signs": True, "has_instruction": True}).status
        is CriterionStatus.PASSED
    )


def test_criterion_02_violation_limiting_rights_without_court_order() -> None:
    result = evaluate(
        2, {"limits_constitutional_rights": True, "has_court_order": False}
    )
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_02_48_hours_norm_rejected() -> None:
    result = evaluate(
        2,
        {
            "limits_constitutional_rights": True,
            "has_court_order": False,
            "used_48h_norm": True,
        },
    )
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_02_passed() -> None:
    assert (
        evaluate(
            2, {"limits_constitutional_rights": True, "has_court_order": True}
        ).status
        is CriterionStatus.PASSED
    )
    assert (
        evaluate(
            2, {"limits_constitutional_rights": False, "has_court_order": False}
        ).status
        is CriterionStatus.PASSED
    )


def test_criterion_03_violation_covert_sts_residential() -> None:
    result = evaluate(
        3,
        {
            "premises_type": "жилое",
            "uses_covert_sts": True,
            "has_residents_consent": False,
            "has_court_order": False,
        },
    )
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_03_passed_with_consent_or_court_order() -> None:
    assert (
        evaluate(
            3,
            {
                "premises_type": "жилое",
                "uses_covert_sts": True,
                "has_residents_consent": True,
                "has_court_order": False,
            },
        ).status
        is CriterionStatus.PASSED
    )
    assert (
        evaluate(
            3,
            {
                "premises_type": "жилое",
                "uses_covert_sts": True,
                "has_residents_consent": False,
                "has_court_order": True,
            },
        ).status
        is CriterionStatus.PASSED
    )


def test_criterion_04_attention_with_consent() -> None:
    result = evaluate(4, {"participant_consent": True})
    assert result.status is CriterionStatus.ATTENTION
    assert result.recommendations


def test_criterion_04_passed_without_consent() -> None:
    assert evaluate(4, {"participant_consent": False}).status is CriterionStatus.PASSED


def test_criterion_05_violation_provocation() -> None:
    for answers in (
        {"coercion": True},
        {"inducement": True},
        {"series_of_provocative_purchases": True},
    ):
        assert evaluate(5, answers).status is CriterionStatus.VIOLATION


def test_criterion_05_passed() -> None:
    assert evaluate(5, {}).status is CriterionStatus.PASSED


def test_criterion_06_violation_residential_against_will() -> None:
    result = evaluate(
        6,
        {
            "premises_type": "жилое",
            "residents_consent": False,
            "has_court_order": False,
            "disguises_search": False,
        },
    )
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_06_violation_disguises_search() -> None:
    result = evaluate(6, {"disguises_search": True})
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_06_passed() -> None:
    assert (
        evaluate(
            6,
            {
                "premises_type": "нежилое",
                "residents_consent": False,
                "has_court_order": False,
            },
        ).status
        is CriterionStatus.PASSED
    )


def test_criterion_07_violation_extension_without_new_data() -> None:
    result = evaluate(7, {"extensions_count": 2, "has_new_materials": False})
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_07_passed() -> None:
    assert (
        evaluate(7, {"extensions_count": 1, "has_new_materials": True}).status
        is CriterionStatus.PASSED
    )
    assert (
        evaluate(7, {"extensions_count": 0, "has_new_materials": False}).status
        is CriterionStatus.PASSED
    )


def test_criterion_08_violation_no_case_storage_over_six_months() -> None:
    result = evaluate(8, {"criminal_case_opened": False, "storage_months": 7})
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_08_passed() -> None:
    assert (
        evaluate(8, {"criminal_case_opened": False, "storage_months": 6}).status
        is CriterionStatus.PASSED
    )
    assert (
        evaluate(8, {"criminal_case_opened": True, "storage_months": 12}).status
        is CriterionStatus.PASSED
    )


def test_criterion_09_violation_no_legalization() -> None:
    result = evaluate(
        9, {"has_legalization": False, "investigative_actions_done": False}
    )
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_09_attention_partial_legalization() -> None:
    result = evaluate(
        9, {"has_legalization": False, "investigative_actions_done": True}
    )
    assert result.status is CriterionStatus.ATTENTION


def test_criterion_09_passed() -> None:
    assert evaluate(9, {"has_legalization": True}).status is CriterionStatus.PASSED


def test_criterion_10_attention_without_copy() -> None:
    result = evaluate(10, {"has_court_order_copy": False})
    assert result.status is CriterionStatus.ATTENTION
    assert any("Истребовать копию" in rec for rec in result.recommendations)


def test_criterion_10_passed() -> None:
    assert evaluate(10, {"has_court_order_copy": True}).status is CriterionStatus.PASSED


def test_criterion_11_attention_person_informed() -> None:
    result = evaluate(11, {"person_informed": True})
    assert result.status is CriterionStatus.ATTENTION


def test_criterion_11_passed() -> None:
    assert evaluate(11, {"person_informed": False}).status is CriterionStatus.PASSED


def test_criterion_12_attention_all_conditions_met() -> None:
    result = evaluate(
        12,
        {
            "guilt_not_established": True,
            "orm_conducted": True,
            "rights_violated": True,
        },
    )
    assert result.status is CriterionStatus.ATTENTION
    assert any("ч. 4 ст. 5" in rec for rec in result.recommendations)


def test_criterion_12_passed() -> None:
    assert evaluate(12, {}).status is CriterionStatus.PASSED


def test_criterion_13_violation_no_defense_attorney() -> None:
    result = evaluate(
        13,
        {
            "rights_restricted": True,
            "orm_type": "оперативный эксперимент",
            "defense_attorney_provided": False,
        },
    )
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_13_passed_exempt_orm_types() -> None:
    assert (
        evaluate(
            13,
            {
                "rights_restricted": True,
                "orm_type": "проверочная закупка",
                "defense_attorney_provided": False,
            },
        ).status
        is CriterionStatus.PASSED
    )
    assert (
        evaluate(
            13,
            {
                "rights_restricted": True,
                "orm_type": "досмотр",
                "defense_attorney_provided": False,
            },
        ).status
        is CriterionStatus.PASSED
    )


def test_criterion_14_violation_detention_without_protocol() -> None:
    result = evaluate(14, {"detention_basis": "задержание", "has_protocol": False})
    assert result.status is CriterionStatus.VIOLATION


def test_criterion_14_passed() -> None:
    assert (
        evaluate(14, {"detention_basis": None, "has_protocol": False}).status
        is CriterionStatus.PASSED
    )
    assert (
        evaluate(14, {"detention_basis": "задержание", "has_protocol": True}).status
        is CriterionStatus.PASSED
    )


def test_priority_for_role_matches_spec() -> None:
    expected = {
        UserRole.lawyer: {2, 5, 6, 9, 10, 13},
        UserRole.investigator: {2, 4, 5, 6, 7},
        UserRole.officer: {1, 2, 3, 5, 6, 7, 8},
        UserRole.admin: set(),
    }
    assert {role: set(PRIORITY_BY_ROLE[role]) for role in expected} == expected


def test_evaluate_all_returns_priority_flags() -> None:
    results = evaluate_criteria(UserRole.lawyer, {})
    priority = {r.criterion_number for r in results if r.priority_for_role}
    assert priority == {2, 5, 6, 9, 10, 13}


def test_evaluate_all_is_fast() -> None:
    started = time.perf_counter()
    results = evaluate_criteria(UserRole.lawyer, {})
    elapsed = time.perf_counter() - started
    assert len(results) == TOTAL_CRITERIA
    assert elapsed < 2.0
