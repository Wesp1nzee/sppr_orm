"""Интеграционные тесты аудита на реальном PostgreSQL.

Требуют ``TEST_DATABASE_URL`` — при его отсутствии весь модуль пропускается.
"""

import pytest
from fakeredis import FakeAsyncRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.audit.models import AuditLogEntry
from app.audit.subscribers import DatabaseAuditWriter, setup_audit_subscribers
from app.auth.models import UserRole
from app.auth.schemas import RegisterRequest
from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.events import EventBus
from app.core.request_context import reset_current_session, set_current_session

pytestmark = pytest.mark.skipif(
    get_settings().test_database_url is None,
    reason="требуется TEST_DATABASE_URL (реальный PostgreSQL)",
)


@pytest.mark.asyncio
async def test_register_writes_audit_entry_on_postgres(
    session_factory: async_sessionmaker[AsyncSession],
    fake_redis: FakeAsyncRedis,
) -> None:
    """End-to-end на PG: регистрация порождает запись ``UserRegistered``.

    Событие публикуется до commit пользователя; подписчик пишет в сессию запроса
    (``current_session``), поэтому FK на ``users.id`` удовлетворяется и в
    PostgreSQL (asyncpg), а ``user_role`` резолвится из identity map.
    """
    bus = EventBus()
    setup_audit_subscribers(
        bus, writer=DatabaseAuditWriter(session_factory=session_factory)
    )

    async with session_factory() as session:
        token = set_current_session(session)
        try:
            service = AuthService(session, fake_redis, events=bus)
            await service.register(
                RegisterRequest(
                    email="pg@example.com",
                    password="password123",
                    full_name="ПГ Тест",
                    role=UserRole.lawyer,
                )
            )
        finally:
            reset_current_session(token)
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(select(AuditLogEntry))
        entries = list(result.scalars())

    assert len(entries) == 1
    assert entries[0].event_type == "UserRegistered"
    assert entries[0].user_id is not None
    assert entries[0].user_role == UserRole.lawyer.value
    assert entries[0].payload["email"] == "pg@example.com"
