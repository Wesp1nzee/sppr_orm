"""Rate limiting: счётчик запросов поверх Redis (фиксированное окно).

Лимитер ключуется по IP клиента и хранится в том же Redis, что и сессии,
поэтому работает при нескольких инстансах приложения (в отличие от in-memory).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request

from app.core.deps import RedisClient
from app.core.exceptions import AppException


def client_ip(request: Request) -> str:
    """IP клиента для ключа лимитера.

    TODO(proxy): за доверенным reverse-proxy брать первый IP из
    ``X-Forwarded-For``, но только если запрос пришёл от доверенного прокси
    (инфраструктура прокси ещё не определена). Сейчас берём ``client.host``.
    """
    if request.client is not None:
        return request.client.host
    return "unknown"


def rate_limit(
    *, scope: str, limit: int, window_seconds: int
) -> Callable[[Request, RedisClient], Awaitable[None]]:
    """Возвращает FastAPI-зависимость: не пускает свыше ``limit`` запросов.

    ``scope`` различает счётчики (например ``login`` и ``register``).
    """

    async def dependency(request: Request, redis: RedisClient) -> None:
        key = f"rate_limit:{scope}:{client_ip(request)}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        if count > limit:
            raise AppException.rate_limited()

    return dependency
