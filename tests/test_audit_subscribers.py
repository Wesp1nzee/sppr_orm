"""Тесты подписчиков аудита: публикация события → запись в ``audit_log_entries``."""

import uuid
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.audit.models import AuditLogEntry
from app.audit.subscribers import DatabaseAuditWriter, setup_audit_subscribers
from app.auth.models import User, UserRole
from app.auth.service import (
    LoginFailed,
    UserLoggedIn,
    UserLoggedOut,
    UserRegistered,
)
from app.checks.service import CheckCreated
from app.core.events import EventBus
from app.documents.models import DocumentType
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

UserFactory = Callable[..., Awaitable[User]]


async def _entries(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, AuditLogEntry]:
    async with session_factory() as session:
        result = await session.execute(select(AuditLogEntry))
        return {e.event_type: e for e in result.scalars()}


@pytest.mark.asyncio
async def test_all_events_persist_with_correct_type_and_payload(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    bus = EventBus()
    setup_audit_subscribers(
        bus, writer=DatabaseAuditWriter(session_factory=session_factory)
    )

    user_id = uuid.uuid4()
    check_id = uuid.uuid4()
    document_id = uuid.uuid4()

    events: list[tuple[str, object]] = [
        ("UserRegistered", UserRegistered(user_id=user_id, email="a@example.com")),
        ("UserLoggedIn", UserLoggedIn(user_id=user_id)),
        ("UserLoggedOut", UserLoggedOut(user_id=user_id)),
        ("LoginFailed", LoginFailed(email="b@example.com")),
        ("CheckCreated", CheckCreated(check_id=check_id, user_id=user_id)),
        (
            "DocumentCreated",
            DocumentCreated(
                document_id=document_id,
                check_id=check_id,
                user_id=user_id,
                document_type=DocumentType.exclusion_motion,
            ),
        ),
        (
            "DocumentFinalized",
            DocumentFinalized(document_id=document_id, user_id=user_id),
        ),
        (
            "DocumentExported",
            DocumentExported(document_id=document_id, user_id=user_id, format="pdf"),
        ),
        (
            "DocumentContentUpdated",
            DocumentContentUpdated(document_id=document_id, user_id=user_id),
        ),
        (
            "NormativeDocumentCreated",
            NormativeDocumentCreated(code="fz-ord-art8", admin_id=user_id),
        ),
        (
            "NormativeDocumentVersionCreated",
            NormativeDocumentVersionCreated(
                code="fz-ord-art8", version=2, admin_id=user_id
            ),
        ),
    ]

    for _, event in events:
        await bus.publish(event)

    entries = await _entries(session_factory)
    assert set(entries) == {name for name, _ in events}

    check = entries["CheckCreated"]
    assert check.user_id == user_id
    assert check.payload["check_id"] == str(check_id)

    document = entries["DocumentCreated"]
    assert document.payload["document_type"] == "exclusion_motion"
    assert document.payload["check_id"] == str(check_id)

    exported = entries["DocumentExported"]
    assert exported.payload["format"] == "pdf"

    version = entries["NormativeDocumentVersionCreated"]
    assert version.payload["version"] == 2
    assert version.user_id == user_id

    failed = entries["LoginFailed"]
    assert failed.user_id is None
    assert failed.payload["email"] == "b@example.com"


@pytest.mark.asyncio
async def test_user_role_snapshot_resolved_from_db(
    session_factory: async_sessionmaker[AsyncSession],
    user_factory: UserFactory,
) -> None:
    user = await user_factory("role@example.com", "password123", UserRole.officer)
    bus = EventBus()
    setup_audit_subscribers(
        bus, writer=DatabaseAuditWriter(session_factory=session_factory)
    )

    await bus.publish(UserLoggedIn(user_id=user.id))

    entries = await _entries(session_factory)
    assert entries["UserLoggedIn"].user_role == UserRole.officer.value
