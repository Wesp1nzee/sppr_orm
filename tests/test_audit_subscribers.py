"""Тесты подписчиков аудита: публикация события → запись в ``audit_log_entries``."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

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
from app.core.request_context import (
    reset_current_client_ip,
    reset_current_session,
    set_current_client_ip,
    set_current_session,
)
from app.db.base import Base
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


@pytest_asyncio.fixture
async def fk_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    await engine.dispose()


async def _entries(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, AuditLogEntry]:
    async with session_factory() as session:
        result = await session.execute(select(AuditLogEntry))
        return {e.event_type: e for e in result.scalars()}


@pytest.mark.asyncio
async def test_all_events_persist_with_correct_type_and_payload(
    session_factory: async_sessionmaker[AsyncSession],
    user_factory: UserFactory,
) -> None:
    user = await user_factory("events@example.com", "password123", UserRole.lawyer)
    bus = EventBus()
    setup_audit_subscribers(
        bus, writer=DatabaseAuditWriter(session_factory=session_factory)
    )

    user_id = user.id
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


@pytest.mark.asyncio
async def test_user_registered_joins_request_session_and_satisfies_fk(
    fk_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Регрессия: событие о ещё не закоммиченном пользователе записывается в БД.

    До фикса подписчик открывал отдельную сессию и вставка падала с
    ``ForeignKeyViolationError`` (пользователь ещё не в ``users``). Теперь запись
    идёт в сессию запроса (``current_session``) — в той же транзакции FK
    удовлетворяется.
    """
    async with fk_session_factory() as session:
        user = User(
            email="new@example.com",
            hashed_password="x",
            full_name="Новый Пользователь",
            role=UserRole.lawyer,
        )
        session.add(user)
        await session.flush()

        writer = DatabaseAuditWriter(session_factory=fk_session_factory)
        token = set_current_session(session)
        try:
            await writer.write(
                event_type="UserRegistered",
                user_id=user.id,
                payload={"user_id": str(user.id), "email": "new@example.com"},
            )
        finally:
            reset_current_session(token)
        await session.commit()

    async with fk_session_factory() as session:
        result = await session.execute(select(AuditLogEntry))
        entries = list(result.scalars())

    assert len(entries) == 1
    assert entries[0].event_type == "UserRegistered"
    assert entries[0].user_id == user.id
    assert entries[0].user_role == UserRole.lawyer.value


@pytest.mark.asyncio
async def test_writer_captures_client_ip(
    session_factory: async_sessionmaker[AsyncSession],
    user_factory: UserFactory,
) -> None:
    user = await user_factory("ip@example.com", "password123", UserRole.lawyer)
    writer = DatabaseAuditWriter(session_factory=session_factory)

    token = set_current_client_ip("203.0.113.7")
    try:
        await writer.write(event_type="UserLoggedIn", user_id=user.id, payload={})
    finally:
        reset_current_client_ip(token)

    entries = await _entries(session_factory)
    assert entries["UserLoggedIn"].ip_address == "203.0.113.7"
