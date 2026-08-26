"""Бизнес-логика домена «Проверки»: запуск, чтение, список, доступ."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.checks.constants import RULES_VERSION, CriterionStatus
from app.checks.models import Check, CriterionResult
from app.checks.repository import CheckRepository, CheckRepositoryProtocol
from app.checks.rules.registry import evaluate_criteria
from app.checks.schemas import (
    CheckCreateRequest,
    CheckListItem,
    CheckOut,
    CheckSummary,
    CriterionResultOut,
)
from app.core.events import EventBus, get_event_bus
from app.core.exceptions import AppException, ErrorCode
from app.core.pagination import PageParams

STATUS_COMPLETED = "completed"


@dataclass(frozen=True)
class CheckCreated:
    check_id: uuid.UUID
    user_id: uuid.UUID


class CheckService:
    def __init__(
        self,
        session: AsyncSession,
        repo: CheckRepositoryProtocol | None = None,
        events: EventBus | None = None,
    ) -> None:
        self._session = session
        self._repo = repo or CheckRepository(session)
        self._events = events or get_event_bus()

    async def create(self, user: User, payload: CheckCreateRequest) -> CheckOut:
        """Запускает проверку по 14 критериям и сохраняет её в БД."""
        domain_results = evaluate_criteria(user.role, payload.answers)

        check = Check(
            user_id=user.id,
            role_at_run=user.role,
            case_title=payload.case_title,
            input_payload=payload.answers,
            status=STATUS_COMPLETED,
            rules_version=RULES_VERSION,
        )
        for result in domain_results:
            check.results.append(
                CriterionResult(
                    criterion_number=result.criterion_number,
                    status=result.status.value,
                    title=result.title,
                    comment=result.comment,
                    legal_references=result.legal_references,
                    recommendations=result.recommendations,
                    priority_for_role=result.priority_for_role,
                )
            )

        await self._repo.add(check)
        await self._events.publish(CheckCreated(check_id=check.id, user_id=user.id))
        return self._to_out(check)

    async def get_for_user(self, user: User, check_id: uuid.UUID) -> CheckOut:
        """Возвращает проверку владельцу или администратору; иначе 404."""
        check = await self._repo.get_by_id(check_id)
        if check is None or (
            check.user_id != user.id and user.role is not UserRole.admin
        ):
            raise AppException(ErrorCode.CHECK_NOT_FOUND)
        return self._to_out(check)

    async def list_for_user(
        self, user: User, page: PageParams
    ) -> tuple[list[CheckListItem], int]:
        """Список проверок: обычный пользователь видит свои, admin — все."""
        user_id = None if user.role is UserRole.admin else user.id
        checks = await self._repo.list_checks(
            user_id=user_id, page=page.page, per_page=page.per_page, sort=page.sort
        )
        total = await self._repo.count(user_id=user_id)
        return [self._to_list_item(check) for check in checks], total

    # --- Преобразование в ответные схемы ------------------------------------

    def _to_out(self, check: Check) -> CheckOut:
        results = _sorted_results(check)
        return CheckOut(
            id=check.id,
            status=check.status,
            summary=_summarize(results),
            priority_criteria_numbers=_priority_numbers(results),
            results=[_result_out(r) for r in results],
            case_title=check.case_title,
            created_at=check.created_at,
        )

    def _to_list_item(self, check: Check) -> CheckListItem:
        results = _sorted_results(check)
        return CheckListItem(
            id=check.id,
            status=check.status,
            summary=_summarize(results),
            priority_criteria_numbers=_priority_numbers(results),
            case_title=check.case_title,
            created_at=check.created_at,
        )


def _sorted_results(check: Check) -> list[CriterionResult]:
    return sorted(check.results, key=lambda r: r.criterion_number)


def _summarize(results: list[CriterionResult]) -> CheckSummary:
    passed = sum(1 for r in results if r.status == CriterionStatus.PASSED.value)
    violations = sum(1 for r in results if r.status == CriterionStatus.VIOLATION.value)
    attention = sum(1 for r in results if r.status == CriterionStatus.ATTENTION.value)
    return CheckSummary(
        total=len(results),
        passed=passed,
        violations=violations,
        attention=attention,
    )


def _priority_numbers(results: list[CriterionResult]) -> list[int]:
    return [r.criterion_number for r in results if r.priority_for_role]


def _result_out(row: CriterionResult) -> CriterionResultOut:
    return CriterionResultOut(
        criterion_number=row.criterion_number,
        title=row.title,
        status=CriterionStatus(row.status),
        comment=row.comment,
        legal_references=row.legal_references,
        recommendations=row.recommendations,
        priority_for_role=row.priority_for_role,
    )


__all__ = ["CheckService"]
