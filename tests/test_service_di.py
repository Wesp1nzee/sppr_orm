"""Тесты DI: сервисы используют подставленный (in-memory) репозиторий."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.auth.models import User, UserRole
from app.auth.schemas import RegisterRequest
from app.auth.service import AuthService
from app.checks.models import Check
from app.checks.schemas import CheckCreateRequest
from app.checks.service import CheckService
from app.core.exceptions import AppException


class FakeUserRepository:
    """In-memory реализация ``UserRepositoryProtocol``."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def get_by_email(self, email: str) -> User | None:
        return self._users.get(email.lower())

    async def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str,
        role: UserRole,
    ) -> User:
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
        )
        user.id = uuid.uuid4()
        user.created_at = datetime.now(UTC)
        self._users[email.lower()] = user
        return user


class FakeCheckRepository:
    """In-memory реализация ``CheckRepositoryProtocol``."""

    def __init__(self) -> None:
        self._checks: dict[uuid.UUID, Check] = {}

    async def add(self, check: Check) -> Check:
        check.id = uuid.uuid4()
        check.created_at = datetime.now(UTC)
        self._checks[check.id] = check
        return check

    async def get_by_id(self, check_id: uuid.UUID) -> Check | None:
        return self._checks.get(check_id)

    async def count(self, *, user_id: uuid.UUID | None = None) -> int:
        if user_id is None:
            return len(self._checks)
        return sum(1 for c in self._checks.values() if c.user_id == user_id)

    async def list_checks(
        self,
        *,
        user_id: uuid.UUID | None,
        page: int,
        per_page: int,
        sort: str | None,
    ) -> list[Check]:
        del page, per_page, sort
        checks = list(self._checks.values())
        if user_id is not None:
            checks = [c for c in checks if c.user_id == user_id]
        return checks


@pytest.mark.asyncio
async def test_auth_service_uses_injected_repository(fake_redis):
    fake = FakeUserRepository()
    service = AuthService(db=None, redis=fake_redis, users=fake)  # type: ignore[arg-type]

    payload = RegisterRequest(
        email="di@example.com", password="password123", full_name="Ди Тест"
    )
    user = await service.register(payload)

    assert user.email == "di@example.com"
    assert await fake.get_by_email("di@example.com") is user

    with pytest.raises(AppException) as exc_info:
        await service.register(payload)
    assert exc_info.value.code.value == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.asyncio
async def test_check_service_uses_injected_repository(fake_redis):
    fake = FakeCheckRepository()
    service = CheckService(session=None, repo=fake)  # type: ignore[arg-type]

    user = User(
        email="owner@example.com",
        hashed_password="x",
        full_name="Владелец",
        role=UserRole.lawyer,
    )
    user.id = uuid.uuid4()

    result = await service.create(user, CheckCreateRequest(answers={}))

    assert result.id in fake._checks
    assert result.status == "completed"
    assert result.summary.total == 14
