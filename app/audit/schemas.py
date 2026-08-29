import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.checks.schemas import CheckSummary, CriterionResultOut
from app.documents.models import DocumentStatus, DocumentType


class AuditLogEntryOut(BaseModel):
    """Представление записи журнала аудита (admin-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    user_id: uuid.UUID | None
    user_role: str | None
    payload: dict[str, Any]
    ip_address: str | None
    created_at: datetime


class AuditLogFilters(BaseModel):
    """Фильтры списка записей журнала аудита (query-параметры)."""

    user_id: uuid.UUID | None = None
    event_type: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class AuditCheckReport(BaseModel):
    """Раздел «проверка» сводного отчёта."""

    id: uuid.UUID
    case_title: str | None
    status: str
    role: str | None
    created_at: datetime
    summary: CheckSummary


class AuditDocumentReport(BaseModel):
    """Раздел «сгенерированные_документы» сводного отчёта."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_type: DocumentType
    title: str
    status: DocumentStatus
    created_at: datetime


class AuditSummaryReportOut(BaseModel):
    """Сводный отчёт по результатам проверки."""

    check: AuditCheckReport
    criterion_results: list[CriterionResultOut]
    documents: list[AuditDocumentReport]
    audit_log: list[AuditLogEntryOut]


__all__ = [
    "AuditCheckReport",
    "AuditDocumentReport",
    "AuditLogEntryOut",
    "AuditLogFilters",
    "AuditSummaryReportOut",
]
