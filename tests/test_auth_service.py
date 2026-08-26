"""Unit-тесты AuthService: правила регистрации и управление сессиями."""

from __future__ import annotations

import json
import time

import pytest

from app.auth.models import UserRole
from app.auth.schemas import RegisterRequest
from app.auth.service import AuthService, session_key
from app.core.exceptions import AppException


def _register_payload(
    email: str = "svc@example.com", role: UserRole = UserRole.lawyer
) -> RegisterRequest:
    return RegisterRequest(
        email=email,
        password="password123",
        full_name="Сервис Тест",
        role=role,
    )


@pytest.mark.asyncio
async def test_register_success_and_duplicate(session_factory, fake_redis):
    async with session_factory() as session:
        service = AuthService(session, fake_redis)
        user = await service.register(_register_payload())
        assert user.email == "svc@example.com"

        with pytest.raises(AppException) as exc_info:
            await service.register(_register_payload())
        assert exc_info.value.status_code == 409
        assert exc_info.value.code.value == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.asyncio
async def test_register_admin_forbidden(session_factory, fake_redis):
    async with session_factory() as session:
        service = AuthService(session, fake_redis)
        with pytest.raises(AppException) as exc_info:
            await service.register(_register_payload(role=UserRole.admin))
        assert exc_info.value.status_code == 403
        assert exc_info.value.code.value == "ADMIN_SELF_REGISTRATION_FORBIDDEN"


@pytest.mark.asyncio
async def test_authenticate_wrong_password_and_inactive(
    session_factory, fake_redis, user_factory
):
    await user_factory(
        "svc@example.com", "password123", UserRole.lawyer, is_active=False
    )
    async with session_factory() as session:
        service = AuthService(session, fake_redis)

        with pytest.raises(AppException) as exc_info:
            await service.authenticate("svc@example.com", "wrong")
        assert exc_info.value.status_code == 401
        assert exc_info.value.code.value == "INVALID_CREDENTIALS"

        with pytest.raises(AppException) as exc_info:
            await service.authenticate("svc@example.com", "password123")
        assert exc_info.value.status_code == 403
        assert exc_info.value.code.value == "ACCOUNT_DEACTIVATED"


@pytest.mark.asyncio
async def test_session_payload_roundtrip(session_factory, fake_redis):
    async with session_factory() as session:
        service = AuthService(session, fake_redis)
        user = await service.register(_register_payload())
        await session.commit()

        sid = await service.create_session(user)
        payload = await service.get_session_payload(sid)
        assert payload is not None
        assert payload["user_id"] == str(user.id)
        assert payload["role"] == UserRole.lawyer.value
        assert payload["hard_expire_at"] > payload["issued_at"]

        await service.refresh_session_ttl(sid)
        assert await fake_redis.ttl(session_key(sid)) > 0

        await service.destroy_session(sid)
        assert await service.get_session_payload(sid) is None


@pytest.mark.asyncio
async def test_get_session_payload_hard_expired(session_factory, fake_redis):
    async with session_factory() as session:
        service = AuthService(session, fake_redis)
        user = await service.register(_register_payload())
        await session.commit()

        sid = await service.create_session(user)
        key = session_key(sid)

        payload = json.loads(await fake_redis.get(key))
        payload["hard_expire_at"] = time.time() - 1
        await fake_redis.set(key, json.dumps(payload))

        assert await service.get_session_payload(sid) is None
        assert await fake_redis.exists(key) == 0


@pytest.mark.asyncio
async def test_get_session_payload_corrupted_deletes_key(session_factory, fake_redis):
    async with session_factory() as session:
        service = AuthService(session, fake_redis)
        user = await service.register(_register_payload())
        await session.commit()

        sid = await service.create_session(user)
        key = session_key(sid)
        await fake_redis.set(key, "{not-json")

        assert await service.get_session_payload(sid) is None
        assert await fake_redis.exists(key) == 0
