import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.auth.repository import UserRepository, UserRepositoryProtocol
from app.auth.schemas import RegisterRequest
from app.core.config import get_settings
from app.core.events import EventBus, get_event_bus
from app.core.exceptions import AppException, ErrorCode
from app.core.security import generate_token, hash_password, verify_password

settings = get_settings()


@dataclass(frozen=True)
class UserRegistered:
    user_id: uuid.UUID
    email: str


@dataclass(frozen=True)
class UserLoggedIn:
    user_id: uuid.UUID


@dataclass(frozen=True)
class UserLoggedOut:
    user_id: uuid.UUID


@dataclass(frozen=True)
class LoginFailed:
    """Событие: неудачная попытка входа (для аудита; rate limiting — отдельно)."""

    email: str


def session_key(sid: str) -> str:
    """Ключ сессии в Redis: ``session:{sid}``."""
    return f"{settings.session_key_prefix}{sid}"


class AuthService:
    """Сервис аутентификации: регистрация, вход, управление сессиями."""

    def __init__(
        self,
        db: AsyncSession,
        redis: Redis,
        users: UserRepositoryProtocol | None = None,
        events: EventBus | None = None,
    ) -> None:
        self._db = db
        self._redis = redis
        self._users = users or UserRepository(db)
        self._events = events or get_event_bus()

    async def register(self, payload: RegisterRequest) -> User:
        existing = await self._users.get_by_email(payload.email)
        if existing is not None:
            raise AppException(ErrorCode.EMAIL_ALREADY_REGISTERED)
        if payload.role is UserRole.admin:
            raise AppException(ErrorCode.ADMIN_SELF_REGISTRATION_FORBIDDEN)

        hashed = hash_password(payload.password)
        user = await self._users.create(
            email=payload.email,
            hashed_password=hashed,
            full_name=payload.full_name.strip(),
            role=payload.role,
        )
        await self._events.publish(UserRegistered(user_id=user.id, email=user.email))
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            await self._events.publish(LoginFailed(email=email))
            raise AppException(ErrorCode.INVALID_CREDENTIALS)
        if not user.is_active:
            await self._events.publish(LoginFailed(email=email))
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
        await self._redis.set(
            session_key(sid), json.dumps(payload), ex=settings.session_ttl_seconds
        )
        await self._events.publish(UserLoggedIn(user_id=user.id))
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
        except (json.JSONDecodeError, TypeError, ValueError):  # fmt: skip
            await self._redis.delete(key)
            return None

        try:
            hard_expire_at = float(data.get("hard_expire_at", 0))
        except (TypeError, ValueError):  # fmt: skip
            hard_expire_at = 0.0
        if time.time() > hard_expire_at:
            await self._redis.delete(key)
            return None

        return data

    async def refresh_session_ttl(self, sid: str) -> None:
        """Скользящее продление TTL сессии (+30 мин от текущего момента)."""
        await self._redis.expire(session_key(sid), settings.session_ttl_seconds)

    async def destroy_session(self, sid: str) -> None:
        payload = await self.get_session_payload(sid)
        await self._redis.delete(session_key(sid))
        if payload is None:
            return
        try:
            user_id = uuid.UUID(str(payload["user_id"]))
        except (KeyError, TypeError, ValueError):  # fmt: skip
            return
        await self._events.publish(UserLoggedOut(user_id=user_id))
