from __future__ import annotations

import json
import time
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.auth.repository import UserRepository
from app.auth.schemas import RegisterRequest
from app.core.config import get_settings
from app.core.exceptions import AppException, ErrorCode
from app.core.security import generate_token, hash_password, verify_password

settings = get_settings()


def session_key(sid: str) -> str:
    """Ключ сессии в Redis: ``session:{sid}``."""
    return f"{settings.session_key_prefix}{sid}"


class AuthService:
    """Сервис аутентификации: регистрация, вход, управление сессиями."""

    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self._db = db
        self._redis = redis
        self._users = UserRepository(db)

    async def register(self, payload: RegisterRequest) -> User:
        existing = await self._users.get_by_email(payload.email)
        if existing is not None:
            raise AppException(ErrorCode.EMAIL_ALREADY_REGISTERED)
        if payload.role is UserRole.admin:
            raise AppException(ErrorCode.ADMIN_SELF_REGISTRATION_FORBIDDEN)

        hashed = hash_password(payload.password)
        return await self._users.create(
            email=payload.email,
            hashed_password=hashed,
            full_name=payload.full_name.strip(),
            role=payload.role,
        )

    async def authenticate(self, email: str, password: str) -> User:
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise AppException(ErrorCode.INVALID_CREDENTIALS)
        if not user.is_active:
            raise AppException(ErrorCode.ACCOUNT_DEACTIVATED)
        return user

    async def create_session(self, user: User) -> str:
        """Создаёт сессию ``session:{sid}`` с TTL 30 мин и жёстким лимитом 12 ч.

        Payload хранит ``hard_expire_at`` — абсолютную точку смерти сессии,
        независимо от скользящего продления TTL.
        """
        sid = generate_token(48)
        now = time.time()
        payload: dict[str, Any] = {
            "user_id": str(user.id),
            "role": user.role.value,
            "issued_at": now,
            "hard_expire_at": now + settings.session_hard_expire_seconds,
        }
        await self._redis.set(session_key(sid), json.dumps(payload), ex=settings.session_ttl_seconds)
        return sid

    async def get_session_payload(self, sid: str) -> dict[str, Any] | None:
        """Возвращает payload сессии или None.

        Возвращает None и удаляет ключ из Redis, если сессия:
        - отсутствует;
        - битая (не JSON / не объект);
        - истекла по жёсткому лимиту ``hard_expire_at`` (12 ч) — независимо
          от скользящего TTL.
        """
        key = session_key(sid)
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError("session payload must be an object")
        except (json.JSONDecodeError, TypeError, ValueError):
            await self._redis.delete(key)
            return None

        try:
            hard_expire_at = float(data.get("hard_expire_at", 0))
        except (TypeError, ValueError):
            hard_expire_at = 0.0
        if time.time() > hard_expire_at:
            await self._redis.delete(key)
            return None

        return data

    async def refresh_session_ttl(self, sid: str) -> None:
        """Скользящее продление TTL сессии (+30 мин от текущего момента)."""
        await self._redis.expire(session_key(sid), settings.session_ttl_seconds)

    async def destroy_session(self, sid: str) -> None:
        await self._redis.delete(session_key(sid))
