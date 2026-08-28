"""Бизнес-логика домена «Логирование/аудит» (ТЗ, раздел 3.5).

Сервис покрывает admin-просмотр журнала, сборку сводного отчёта по проверке
(JSON + экспорт DOCX/PDF) и ретеншен журнала. Сама запись событий в журнал
выполняется подписчиками ``EventBus`` (``app/audit/subscribers.py``).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository, AuditLogRepositoryProtocol
from app.audit.schemas import (
    AuditCheckReport,
    AuditDocumentReport,
    AuditLogEntryOut,
    AuditLogFilters,
    AuditSummaryReportOut,
)
from app.auth.models import User, UserRole
from app.checks.constants import CriterionStatus
from app.checks.models import CriterionResult
from app.checks.repository import CheckRepository
from app.checks.schemas import CheckSummary, CriterionResultOut
from app.core.exceptions import AppException, ErrorCode
from app.core.pagination import PageParams
from app.documents.export import export_docx, export_pdf
from app.documents.repository import GeneratedDocumentRepository
from app.knowledge_base.schemas import NormativeReferenceOut

ExportFormat = Literal["docx", "pdf"]

#: Максимум документов проверки, включаемых в сводный отчёт (защита от пагинации).
_MAX_REPORT_DOCS = 1000


class AuditService:
    def __init__(
        self,
        session: AsyncSession,
        repo: AuditLogRepositoryProtocol | None = None,
    ) -> None:
        self._session = session
        self._repo = repo or AuditLogRepository(session)

    async def list_for_admin(
        self, *, filters: AuditLogFilters, page: PageParams
    ) -> tuple[list[AuditLogEntryOut], int]:
        entries = await self._repo.list_entries(
            user_id=filters.user_id,
            event_type=filters.event_type,
            date_from=filters.date_from,
            date_to=filters.date_to,
            page=page.page,
            per_page=page.per_page,
            sort=page.sort,
        )
        total = await self._repo.count(
            user_id=filters.user_id,
            event_type=filters.event_type,
            date_from=filters.date_from,
            date_to=filters.date_to,
        )
        return [AuditLogEntryOut.model_validate(e) for e in entries], total

    async def get_for_admin(self, entry_id: uuid.UUID) -> AuditLogEntryOut:
        entry = await self._repo.get_by_id(entry_id)
        if entry is None:
            raise AppException(ErrorCode.AUDIT_LOG_ENTRY_NOT_FOUND)
        return AuditLogEntryOut.model_validate(entry)

    async def get_summary_report(
        self, check_id: uuid.UUID, requester: User
    ) -> AuditSummaryReportOut:
        """Сводный отчёт: проверка + критерии + документы + журнал действий.

        Доступ — владелец проверки ИЛИ admin (ТЗ 3.5 ограничивает полным
        доступом только журналы аудита; отчёт по собственной проверке доступен
        пользователю).
        """
        check = await CheckRepository(self._session).get_by_id(check_id)
        if check is None or (
            check.user_id != requester.id and requester.role is not UserRole.admin
        ):
            raise AppException(ErrorCode.CHECK_NOT_FOUND)

        documents = await GeneratedDocumentRepository(self._session).list_for_check(
            check_id=check_id, page=1, per_page=_MAX_REPORT_DOCS
        )
        entries = await self._repo.list_for_check(check_id, [d.id for d in documents])
        results = sorted(check.results, key=lambda r: r.criterion_number)
        return AuditSummaryReportOut(
            check=AuditCheckReport(
                id=check.id,
                case_title=check.case_title,
                status=check.status,
                role=check.role_at_run.value,
                created_at=check.created_at,
                summary=_summarize(results),
            ),
            criterion_results=[_result_out(r) for r in results],
            documents=[AuditDocumentReport.model_validate(d) for d in documents],
            audit_log=[AuditLogEntryOut.model_validate(e) for e in entries],
        )

    async def export_summary_report(
        self, check_id: uuid.UUID, requester: User, format: ExportFormat
    ) -> bytes:
        """Экспорт сводного отчёта в DOCX/PDF через ``app.documents.export``."""
        report = await self.get_summary_report(check_id, requester)
        content = _report_content(report)
        title = f"Сводный отчёт по проверке {check_id}"
        if format == "docx":
            return export_docx(content, title)
        return export_pdf(content, title)

    async def purge_expired(self, retention_days: int = 365) -> int:
        """Удаляет записи старше ``retention_days`` (ТЗ, раздел 4 — ≥ 1 года)."""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        return await self._repo.delete_older_than(cutoff)


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


def _result_out(row: CriterionResult) -> CriterionResultOut:
    return CriterionResultOut(
        criterion_number=row.criterion_number,
        title=row.title,
        status=CriterionStatus(row.status),
        comment=row.comment,
        legal_references=[NormativeReferenceOut(**ref) for ref in row.legal_references],
        recommendations=row.recommendations,
        priority_for_role=row.priority_for_role,
    )


def _report_content(report: AuditSummaryReportOut) -> dict[str, Any]:
    """Структурированный контент отчёта для рендера DOCX/PDF (русские ключи)."""
    check = report.check
    return {
        "проверка": {
            "название_дела": check.case_title or "",
            "роль": check.role or "",
            "дата_проверки": check.created_at.isoformat(),
            "сводка": (
                f"всего: {check.summary.total}, пройдено: {check.summary.passed}, "
                f"нарушений: {check.summary.violations}, "
                f"требуют внимания: {check.summary.attention}"
            ),
        },
        "результаты_по_критериям": [
            {
                "criterion_number": r.criterion_number,
                "title": r.title,
                "status": r.status.value,
                "comment": r.comment,
                "recommendations": ", ".join(r.recommendations),
            }
            for r in report.criterion_results
        ],
        "сгенерированные_документы": [
            {
                "document_type": d.document_type.value,
                "title": d.title,
                "status": d.status.value,
                "created_at": d.created_at.isoformat(),
            }
            for d in report.documents
        ],
        "журнал_действий": [
            {
                "event_type": e.event_type,
                "user_role": e.user_role or "",
                "created_at": e.created_at.isoformat(),
            }
            for e in report.audit_log
        ],
    }


__all__ = ["AuditService"]
