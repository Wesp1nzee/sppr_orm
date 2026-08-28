"""Unit-тесты AuditService: список/фильтры, отчёт, ретеншен."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.audit.models import AuditLogEntry
from app.audit.repository import AuditLogRepository
from app.audit.schemas import AuditLogFilters
from app.audit.service import AuditService
from app.auth.models import User, UserRole
from app.checks.schemas import CheckCreateRequest
from app.checks.service import CheckService
from app.core.exceptions import AppException
from app.core.pagination import PageParams
from app.documents.models import DocumentStatus, DocumentType, GeneratedDocument
from app.documents.repository import GeneratedDocumentRepository


async def _make_user(session: AsyncSession, email: str, role: UserRole) -> User:
    user = User(email=email, hashed_password="x", full_name="Тест", role=role)
    session.add(user)
    await session.flush()
    return user


async def _make_check(
    session: AsyncSession, user: User, *, case_title: str | None = "Дело"
) -> uuid.UUID:
    return (
        await CheckService(session).create(
            user, CheckCreateRequest(answers={}, case_title=case_title)
        )
    ).id


@pytest.mark.asyncio
async def test_list_for_admin_filters_and_pagination(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        user_a = await _make_user(session, "a@example.com", UserRole.lawyer)
        user_b = await _make_user(session, "b@example.com", UserRole.officer)
        repo = AuditLogRepository(session)
        await repo.add(
            AuditLogEntry(event_type="CheckCreated", user_id=user_a.id, payload={})
        )
        await repo.add(
            AuditLogEntry(event_type="UserLoggedIn", user_id=user_a.id, payload={})
        )
        await repo.add(
            AuditLogEntry(event_type="CheckCreated", user_id=user_b.id, payload={})
        )
        await session.commit()

    async with session_factory() as session:
        service = AuditService(session)

        items, total = await service.list_for_admin(
            filters=AuditLogFilters(), page=PageParams()
        )
        assert total == 3
        assert len(items) == 3

        by_user, total_by_user = await service.list_for_admin(
            filters=AuditLogFilters(user_id=user_a.id), page=PageParams()
        )
        assert total_by_user == 2
        assert {e.event_type for e in by_user} == {"CheckCreated", "UserLoggedIn"}

        by_type, total_by_type = await service.list_for_admin(
            filters=AuditLogFilters(event_type="CheckCreated"), page=PageParams()
        )
        assert total_by_type == 2
        assert {e.event_type for e in by_type} == {"CheckCreated"}

        page_one, total_paged = await service.list_for_admin(
            filters=AuditLogFilters(), page=PageParams(page=1, per_page=2)
        )
        assert total_paged == 3
        assert len(page_one) == 2


@pytest.mark.asyncio
async def test_get_for_admin_missing_raises(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = AuditService(session)
        with pytest.raises(AppException) as exc_info:
            await service.get_for_admin(uuid.uuid4())
        assert exc_info.value.code.value == "AUDIT_LOG_ENTRY_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_summary_report_for_owner(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        user = await _make_user(session, "owner@example.com", UserRole.lawyer)
        check_id = await _make_check(session, user, case_title="Дело №1")

        doc = GeneratedDocument(
            check_id=check_id,
            user_id=user.id,
            document_type=DocumentType.exclusion_motion,
            status=DocumentStatus.finalized,
            title="Ходатайство",
            content={},
            template_version="1.0.0",
        )
        await GeneratedDocumentRepository(session).add(doc)

        repo = AuditLogRepository(session)
        await repo.add(
            AuditLogEntry(
                event_type="CheckCreated",
                user_id=user.id,
                payload={"check_id": str(check_id)},
            )
        )
        await repo.add(
            AuditLogEntry(
                event_type="DocumentCreated",
                user_id=user.id,
                payload={"check_id": str(check_id), "document_id": str(doc.id)},
            )
        )
        await repo.add(
            AuditLogEntry(event_type="UserLoggedIn", user_id=user.id, payload={})
        )
        await session.commit()

    async with session_factory() as session:
        report = await AuditService(session).get_summary_report(check_id, user)

        assert report.check.case_title == "Дело №1"
        assert report.check.role == UserRole.lawyer.value
        assert report.check.summary.total == 14
        assert len(report.criterion_results) == 14
        assert len(report.documents) == 1
        assert report.documents[0].id == doc.id
        assert {e.event_type for e in report.audit_log} == {
            "CheckCreated",
            "DocumentCreated",
        }


@pytest.mark.asyncio
async def test_get_summary_report_for_non_owner_raises(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        owner = await _make_user(session, "owner@example.com", UserRole.lawyer)
        stranger = await _make_user(session, "stranger@example.com", UserRole.lawyer)
        check_id = await _make_check(session, owner)
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(AppException) as exc_info:
            await AuditService(session).get_summary_report(check_id, stranger)
        assert exc_info.value.code.value == "CHECK_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_summary_report_for_admin(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        owner = await _make_user(session, "owner@example.com", UserRole.lawyer)
        admin = await _make_user(session, "admin@example.com", UserRole.admin)
        check_id = await _make_check(session, owner)
        await session.commit()

    async with session_factory() as session:
        report = await AuditService(session).get_summary_report(check_id, admin)
        assert report.check.id == check_id


@pytest.mark.asyncio
async def test_purge_expired(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    old = datetime.now(UTC) - timedelta(days=400)
    recent = datetime.now(UTC) - timedelta(days=10)

    async with session_factory() as session:
        repo = AuditLogRepository(session)
        await repo.add(
            AuditLogEntry(
                event_type="CheckCreated", user_id=None, payload={}, created_at=old
            )
        )
        await repo.add(
            AuditLogEntry(
                event_type="CheckCreated", user_id=None, payload={}, created_at=recent
            )
        )
        await session.commit()

    async with session_factory() as session:
        deleted = await AuditService(session).purge_expired(retention_days=365)
        await session.commit()

    assert deleted == 1

    async with session_factory() as session:
        remaining = await AuditLogRepository(session).count(
            user_id=None, event_type=None, date_from=None, date_to=None
        )
    assert remaining == 1
