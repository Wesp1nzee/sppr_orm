"""Подписчики ``EventBus`` домена «Аудит»: записывают события в ``audit_log_entries``.

Подписчики работают вне HTTP request-scope и открывают собственную сессию БД
через ``async_session_factory``. ``EventBus.publish`` — fire-and-forget: он
глотает и логирует исключения обработчиков, поэтому ошибка записи аудита не
роняет источник события.

Асинхронная запись через фоновую очередь (ARQ/Redis, ``app/workers``) не
реализована в этой итерации — seam для неё оставлен в виде интерфейса
``AuditWriter`` (см. ``DatabaseAuditWriter``).
"""

import uuid
from dataclasses import asdict
from enum import Enum
from functools import partial
from typing import Any, Protocol, cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.audit.models import AuditLogEntry
from app.audit.repository import AuditLogRepository
from app.auth.repository import UserRepository
from app.auth.service import LoginFailed, UserLoggedIn, UserLoggedOut, UserRegistered
from app.checks.service import CheckCreated
from app.core.events import EventBus
from app.db.session import async_session_factory
from app.documents.service import (
    DocumentContentUpdated,
    DocumentCreated,
    DocumentExported,
    DocumentFinalized,
)
from app.knowledge_base.service import (
    NormativeDocumentCreated,
    NormativeDocumentVersionCreated,
)


class AuditWriter(Protocol):
    """Интерфейс записи аудита: сейчас БД, позже — постановка в очередь (ARQ)."""

    async def write(
        self,
        *,
        event_type: str,
        user_id: uuid.UUID | None,
        payload: dict[str, Any],
    ) -> None: ...


class DatabaseAuditWriter:
    """Синхронная запись в БД в собственной сессии.

    TODO(audit, ARQ): при появлении очереди реализовать ``AuditWriter``,
    ставящий задачу в очередь, не меняя сигнатуры подписчиков.
    """

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession] | None = None
    ) -> None:
        self._session_factory = session_factory or async_session_factory

    async def write(
        self,
        *,
        event_type: str,
        user_id: uuid.UUID | None,
        payload: dict[str, Any],
    ) -> None:
        async with self._session_factory() as session:
            entry = AuditLogEntry(
                event_type=event_type,
                user_id=user_id,
                user_role=await _resolve_role(session, user_id),
                payload=payload,
            )
            await AuditLogRepository(session).add(entry)
            await session.commit()


async def _resolve_role(session: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    """Снимок роли пользователя на момент обработки события."""
    if user_id is None:
        return None
    user = await UserRepository(session).get_by_id(user_id)
    return user.role.value if user else None


def _jsonable(value: Any) -> Any:
    """Приводит dataclass-событие к JSON-совместимому словарю (UUID → str)."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _payload(event: Any) -> dict[str, Any]:
    return cast(dict[str, Any], _jsonable(asdict(event)))


async def _on_user_registered(writer: AuditWriter, event: UserRegistered) -> None:
    await writer.write(
        event_type="UserRegistered",
        user_id=event.user_id,
        payload=_payload(event),
    )


async def _on_user_logged_in(writer: AuditWriter, event: UserLoggedIn) -> None:
    await writer.write(
        event_type="UserLoggedIn",
        user_id=event.user_id,
        payload=_payload(event),
    )


async def _on_user_logged_out(writer: AuditWriter, event: UserLoggedOut) -> None:
    await writer.write(
        event_type="UserLoggedOut",
        user_id=event.user_id,
        payload=_payload(event),
    )


async def _on_login_failed(writer: AuditWriter, event: LoginFailed) -> None:
    await writer.write(
        event_type="LoginFailed",
        user_id=None,
        payload=_payload(event),
    )


async def _on_check_created(writer: AuditWriter, event: CheckCreated) -> None:
    await writer.write(
        event_type="CheckCreated",
        user_id=event.user_id,
        payload=_payload(event),
    )


async def _on_document_created(writer: AuditWriter, event: DocumentCreated) -> None:
    await writer.write(
        event_type="DocumentCreated",
        user_id=event.user_id,
        payload=_payload(event),
    )


async def _on_document_finalized(writer: AuditWriter, event: DocumentFinalized) -> None:
    await writer.write(
        event_type="DocumentFinalized",
        user_id=event.user_id,
        payload=_payload(event),
    )


async def _on_document_exported(writer: AuditWriter, event: DocumentExported) -> None:
    await writer.write(
        event_type="DocumentExported",
        user_id=event.user_id,
        payload=_payload(event),
    )


async def _on_document_content_updated(
    writer: AuditWriter, event: DocumentContentUpdated
) -> None:
    await writer.write(
        event_type="DocumentContentUpdated",
        user_id=event.user_id,
        payload=_payload(event),
    )


async def _on_normative_document_created(
    writer: AuditWriter, event: NormativeDocumentCreated
) -> None:
    await writer.write(
        event_type="NormativeDocumentCreated",
        user_id=event.admin_id,
        payload=_payload(event),
    )


async def _on_normative_document_version_created(
    writer: AuditWriter, event: NormativeDocumentVersionCreated
) -> None:
    await writer.write(
        event_type="NormativeDocumentVersionCreated",
        user_id=event.admin_id,
        payload=_payload(event),
    )


def setup_audit_subscribers(
    bus: EventBus, *, writer: AuditWriter | None = None
) -> None:
    """Регистрирует подписчиков на все доменные события (сохранение в БД)."""
    w = writer or DatabaseAuditWriter()
    bus.subscribe(UserRegistered, partial(_on_user_registered, w))
    bus.subscribe(UserLoggedIn, partial(_on_user_logged_in, w))
    bus.subscribe(UserLoggedOut, partial(_on_user_logged_out, w))
    bus.subscribe(LoginFailed, partial(_on_login_failed, w))
    bus.subscribe(CheckCreated, partial(_on_check_created, w))
    bus.subscribe(DocumentCreated, partial(_on_document_created, w))
    bus.subscribe(DocumentFinalized, partial(_on_document_finalized, w))
    bus.subscribe(DocumentExported, partial(_on_document_exported, w))
    bus.subscribe(DocumentContentUpdated, partial(_on_document_content_updated, w))
    bus.subscribe(NormativeDocumentCreated, partial(_on_normative_document_created, w))
    bus.subscribe(
        NormativeDocumentVersionCreated,
        partial(_on_normative_document_version_created, w),
    )


__all__ = ["AuditWriter", "DatabaseAuditWriter", "setup_audit_subscribers"]
