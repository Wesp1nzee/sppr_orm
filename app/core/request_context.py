"""Контекст текущего запроса: активная сессия БД и IP-адрес клиента.

Используется подписчиками ``EventBus`` (``app/audit``), которые работают вне
HTTP request-scope: ``current_session`` — ``AsyncSession`` текущего запроса
(устанавливается в ``app.db.session.get_db``), ``current_client_ip`` — IP
клиента (устанавливается middleware в ``app.main``). Вне запроса оба значения
``None``, и потребители должны корректно это обрабатывать.
"""

from contextvars import ContextVar, Token

from sqlalchemy.ext.asyncio import AsyncSession

_current_session: ContextVar[AsyncSession | None] = ContextVar(
    "request_session", default=None
)
_current_client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)


def get_current_session() -> AsyncSession | None:
    return _current_session.get()


def set_current_session(session: AsyncSession | None) -> Token[AsyncSession | None]:
    return _current_session.set(session)


def reset_current_session(token: Token[AsyncSession | None]) -> None:
    _current_session.reset(token)


def get_current_client_ip() -> str | None:
    return _current_client_ip.get()


def set_current_client_ip(ip: str | None) -> Token[str | None]:
    return _current_client_ip.set(ip)


def reset_current_client_ip(token: Token[str | None]) -> None:
    _current_client_ip.reset(token)


__all__ = [
    "get_current_client_ip",
    "get_current_session",
    "reset_current_client_ip",
    "reset_current_session",
    "set_current_client_ip",
    "set_current_session",
]
