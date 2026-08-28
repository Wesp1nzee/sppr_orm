"""Эндпоинты домена «Логирование/аудит» 
Журналы аудита доступны только администратору Сводный
отчёт по результатам проверки доступен владельцу проверки ИЛИ администратору —
ТЗ ограничивает полным доступом именно журналы, а не отчёт по собственной
проверке пользователя.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, Query, Response

from app.audit.schemas import (
    AuditLogEntryOut,
    AuditLogFilters,
    AuditSummaryReportOut,
)
from app.audit.service import AuditService
from app.auth.dependencies import CurrentUser, require_roles
from app.auth.models import User, UserRole
from app.core.deps import DbSession
from app.core.pagination import PageParams, get_page_params
from app.core.routing import ApiRouter
from app.core.schemas import DataResponse, PageMeta

router = ApiRouter(prefix="/audit", tags=["audit"])

AdminUser = Annotated[User, Depends(require_roles(UserRole.admin))]

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
PDF_MEDIA_TYPE = "application/pdf"


@router.get(
    "/logs",
    response_model=DataResponse[list[AuditLogEntryOut]],
    summary="Список записей журнала аудита (только admin)",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        403: {"description": "INSUFFICIENT_PERMISSIONS — недостаточно прав"},
    },
)
async def list_audit_logs(
    admin: AdminUser,
    db: DbSession,
    page: Annotated[PageParams, Depends(get_page_params)],
    user_id: Annotated[uuid.UUID | None, Query()] = None,
    event_type: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> DataResponse[list[AuditLogEntryOut]]:
    filters = AuditLogFilters(
        user_id=user_id,
        event_type=event_type,
        date_from=date_from,
        date_to=date_to,
    )
    items, total = await AuditService(db).list_for_admin(filters=filters, page=page)
    return DataResponse[list[AuditLogEntryOut]](
        data=items,
        meta=PageMeta(page=page.page, per_page=page.per_page, total=total),
    )


@router.get(
    "/logs/{entry_id}",
    response_model=DataResponse[AuditLogEntryOut],
    summary="Запись журнала аудита по id (только admin)",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        403: {"description": "INSUFFICIENT_PERMISSIONS — недостаточно прав"},
        404: {"description": "AUDIT_LOG_ENTRY_NOT_FOUND — запись не найдена"},
    },
)
async def get_audit_log_entry(
    entry_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
) -> DataResponse[AuditLogEntryOut]:
    entry = await AuditService(db).get_for_admin(entry_id)
    return DataResponse[AuditLogEntryOut](data=entry)


@router.get(
    "/reports/{check_id}/summary",
    response_model=DataResponse[AuditSummaryReportOut],
    summary="Сводный отчёт по результатам проверки (владелец или admin)",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        404: {"description": "CHECK_NOT_FOUND — проверка не найдена"},
    },
)
async def get_summary_report(
    check_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[AuditSummaryReportOut]:
    """Отчёт по проверке: проверка, критерии, документы, журнал действий.

    Доступ — владелец проверки ИЛИ admin. В отличие от ``/audit/logs`` здесь
    используется ``CurrentUser`` (не ``require_roles(admin)``): ТЗ 3.5
    ограничивает полным доступом журналы аудита, а отчёт по собственной
    проверке — данные пользователя, поэтому он доступен и владельцу.
    """
    report = await AuditService(db).get_summary_report(check_id, user)
    return DataResponse[AuditSummaryReportOut](data=report)


@router.get(
    "/reports/{check_id}/export",
    summary="Экспорт сводного отчёта в DOCX или PDF (владелец или admin)",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        404: {"description": "CHECK_NOT_FOUND — проверка не найдена"},
    },
)
async def export_summary_report(
    check_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    format: Annotated[Literal["docx", "pdf"], Query()] = "docx",
) -> Response:
    content = await AuditService(db).export_summary_report(check_id, user, format)
    if format == "pdf":
        media_type = PDF_MEDIA_TYPE
        extension = "pdf"
    else:
        media_type = DOCX_MEDIA_TYPE
        extension = "docx"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="audit_report_{check_id}.{extension}"'
            )
        },
    )


__all__ = ["router"]
