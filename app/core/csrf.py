"""CSRF-защита по паттерну double-submit cookie

Сервер выставляет cookie ``csrf_token`` (не HttpOnly — фронт должен её читать).
Фронт обязан дублировать значение в заголовке ``X-CSRF-Token`` на каждый
мутирующий запрос (POST/PUT/PATCH/DELETE). Middleware сверяет cookie и header.
"""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

_CSRF_ERROR_BODY: dict = {
    "error": {
        "code": "CSRF_TOKEN_INVALID",
        "message": "Неверный или отсутствующий CSRF-токен",
        "details": [],
    }
}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_error_response() -> JSONResponse:
    return JSONResponse(status_code=403, content=_CSRF_ERROR_BODY)


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        cookie_name: str,
        header_name: str,
        exempt_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._cookie_name = cookie_name
        self._header_name = header_name
        self._exempt_paths = frozenset(exempt_paths or [])

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method.upper() in SAFE_METHODS:
            return await call_next(request)
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        cookie_token = request.cookies.get(self._cookie_name)
        header_token = request.headers.get(self._header_name)
        if (
            not cookie_token
            or not header_token
            or not secrets.compare_digest(cookie_token, header_token)
        ):
            return csrf_error_response()

        return await call_next(request)
