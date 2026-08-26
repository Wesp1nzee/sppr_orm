from __future__ import annotations

import json
import time
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.security import generate_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest

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
            raise AppException.conflict("Пользователь с таким email уже зарегистрирован")
        if payload.role is UserRole.admin:
            raise AppException.forbidden("Самостоятельная регистрация администратора запрещена")

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
            raise AppException.unauthenticated("Неверный email или пароль")
        if not user.is_active:
            raise AppException.forbidden("Учётная запись деактивирована")
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
        raw = await self._redis.get(session_key(sid))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    async def refresh_session_ttl(self, sid: str) -> None:
        await self._redis.expire(session_key(sid), settings.session_ttl_seconds)

    async def destroy_session(self, sid: str) -> None:
        await self._redis.delete(session_key(sid))
