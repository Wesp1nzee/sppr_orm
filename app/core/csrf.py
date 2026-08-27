"""CSRF-защита: подписанный double-submit cookie, привязанный к сессии.

Схема (OWASP CSRF Prevention Cheat Sheet, вариант "Signed Double-Submit
Cookie"): cookie ``csrf_token`` хранит ``HMAC-SHA256(secret_key, sid)``,
где ``sid`` — идентификатор сессии из HttpOnly-cookie. Фронт дублирует
значение cookie в заголовок ``X-CSRF-Token`` на каждый мутирующий запрос
(POST/PUT/PATCH/DELETE). Middleware проверяет два условия:

1. cookie == header (double-submit);
2. cookie является корректным HMAC для текущего ``sid`` из cookie сессии.

Привязка к сессии закрывает cookie-injection атаки (через поддомен/MITM),
из-за которых «наивный» double-submit считается уязвимым: атакующий может
подсунуть браузеру произвольную пару cookie+header, но не может вычислить
HMAC для чужого ``sid`` — ``secret_key`` ему неизвестен. Все сравнения —
только через ``secrets.compare_digest``.

Если сессии ещё нет (запросы до логина, например register), ``sid`` пуст
и токен равен ``HMAC(secret_key, b"")`` — в этом случае работает обычный
double-submit, т.к. привязываться к сессии ещё не к чему.
"""

import hashlib
import hmac
import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import get_settings
from app.core.exceptions import ErrorCode
from app.core.messages import DEFAULT_LOCALE, get_message, resolve_locale

SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def generate_csrf_token(sid: str | None = None) -> str:
    """Возвращает ``HMAC-SHA256(secret_key, sid)`` — токен, привязанный к сессии.

    ``sid=None`` (до логина) → HMAC от пустой строки.
    """
    return _hmac_for_sid(get_settings().secret_key, sid)


def _hmac_for_sid(secret_key: str, sid: str | None) -> str:
    message = sid.encode("utf-8") if sid else b""
    return hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def csrf_error_response(request: Request) -> JSONResponse:
    """403 в формате api.md с локализованным сообщением CSRF_TOKEN_INVALID."""
    locale = resolve_locale(request) if request is not None else DEFAULT_LOCALE
    body = {
        "error": {
            "code": ErrorCode.CSRF_TOKEN_INVALID.value,
            "message": get_message(ErrorCode.CSRF_TOKEN_INVALID, locale),
            "details": [],
        }
    }
    return JSONResponse(status_code=403, content=body)


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        cookie_name: str,
        header_name: str,
        session_cookie_name: str,
        secret_key: str,
        exempt_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._cookie_name = cookie_name
        self._header_name = header_name
        self._session_cookie_name = session_cookie_name
        self._secret_key = secret_key
        self._exempt_paths = frozenset(exempt_paths or [])

    def _expected_token(self, sid: str | None) -> str:
        return _hmac_for_sid(self._secret_key, sid)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method.upper() in SAFE_METHODS:
            return await call_next(request)
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        cookie_token = request.cookies.get(self._cookie_name)
        header_token = request.headers.get(self._header_name)
        if not cookie_token or not header_token:
            return csrf_error_response(request)

        sid = request.cookies.get(self._session_cookie_name)
        expected = self._expected_token(sid)
        if not secrets.compare_digest(
            cookie_token, header_token
        ) or not secrets.compare_digest(cookie_token, expected):
            return csrf_error_response(request)

        return await call_next(request)
