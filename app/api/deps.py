"""FastAPI-зависимости: БД, Redis, текущий пользователь, RBAC."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.users import UserRepository
from app.services.auth_service import session_key

settings = get_settings()

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


RedisClient = Annotated[Redis, Depends(get_redis)]


async def get_current_user(
    request: Request,
    db: DbSession,
    redis: RedisClient,
) -> User:
    """Достаёт пользователя из Redis-сессии по cookie ``sid``.

    - нет cookie / нет сессии в Redis → 401 UNAUTHENTICATED;
    - жёсткий лимит 12 ч превышен → сессия удаляется, 401;
    - пользователь неактивен → сессия удаляется, 401;
    - при успехе TTL продлевается (скользящее продление, 30 мин).
    """
    sid = request.cookies.get(settings.session_cookie_name)
    if not sid:
        raise AppException.unauthenticated("Сессия не найдена, выполните вход")

    key = session_key(sid)
    raw = await redis.get(key)
    if raw is None:
        raise AppException.unauthenticated("Сессия не найдена или истекла, выполните вход")

    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("session payload must be an object")
    except (json.JSONDecodeError, TypeError, ValueError):
        await redis.delete(key)
        raise AppException.unauthenticated("Сессия повреждена, выполните вход")

    if time.time() > float(payload.get("hard_expire_at", 0)):
        await redis.delete(key)
        raise AppException.unauthenticated("Сессия истекла, выполните вход повторно")

    try:
        user_id = uuid.UUID(str(payload["user_id"]))
    except (KeyError, TypeError, ValueError):
        await redis.delete(key)
        raise AppException.unauthenticated("Сессия повреждена, выполните вход")

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        await redis.delete(key)
        raise AppException.unauthenticated("Пользователь не найден или деактивирован")

    # +30 мин от каждого аутентифицированного запроса.
    await redis.expire(key, settings.session_ttl_seconds)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: UserRole) -> Callable[[CurrentUser], Awaitable[User]]:
    """RBAC-зависимость: пускает только перечисленные роли (api.md, раздел 3)."""

    async def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppException.forbidden("Недостаточно прав для выполнения операции")
        return user

    return checker
