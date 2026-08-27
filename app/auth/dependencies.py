import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyCookie

from app.auth.models import User, UserRole
from app.auth.repository import UserRepository
from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.deps import DbSession, RedisClient
from app.core.exceptions import AppException, ErrorCode

settings = get_settings()

session_scheme = APIKeyCookie(
    name=settings.session_cookie_name,
    description="Сессионный cookie, выдаваемый при входе через /auth/login",
    auto_error=False,
)


async def get_current_user(
    db: DbSession,
    redis: RedisClient,
    sid: str | None = Security(session_scheme),
) -> User:
    """Достаёт пользователя из Redis-сессии по cookie ``sid``.

    - нет cookie / нет сессии в Redis → 401;
    - жёсткий лимит 12 ч превышен → сессия удаляется, 401;
    - пользователь неактивен → сессия удаляется, 401;
    - при успехе TTL продлевается (скользящее продление, 30 мин).

    Парсинг Redis-сессии и проверка ``hard_expire_at`` — в
    ``AuthService.get_session_payload``; здесь только пользовательская
    логика поверх её результата.
    """
    if not sid:
        raise AppException(ErrorCode.SESSION_NOT_FOUND)

    service = AuthService(db, redis)
    payload = await service.get_session_payload(sid)
    if payload is None:
        raise AppException(ErrorCode.SESSION_NOT_FOUND)

    try:
        user_id = uuid.UUID(str(payload["user_id"]))
    except (KeyError, TypeError, ValueError):  # fmt: skip
        await service.destroy_session(sid)
        raise AppException(ErrorCode.SESSION_CORRUPTED) from None

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        await service.destroy_session(sid)
        raise AppException(ErrorCode.USER_NOT_FOUND_OR_INACTIVE)

    # +30 мин от каждого аутентифицированного запроса.
    await service.refresh_session_ttl(sid)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: UserRole) -> Callable[[CurrentUser], Awaitable[User]]:
    """RBAC-зависимость: пускает только перечисленные роли (api.md, раздел 3)."""

    async def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppException(ErrorCode.INSUFFICIENT_PERMISSIONS)
        return user

    return checker


__all__ = ["CurrentUser", "get_current_user", "require_roles"]
