"""FastAPI application factory: CORS, CSRF, exception handlers, lifespan."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import from_url as redis_from_url
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.audit import setup_audit_subscribers
from app.core.config import get_settings
from app.core.csrf import CSRFMiddleware
from app.core.events import get_event_bus
from app.core.exceptions import AppException, ErrorCode
from app.core.messages import get_message, resolve_locale
from app.core.schemas import ErrorBody, ErrorDetail, ErrorResponse

logger = logging.getLogger("sppr_orm")
settings = get_settings()


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details or [])
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_audit_subscribers(get_event_bus())
    app.state.redis = redis_from_url(settings.redis_url, decode_responses=True)
    try:
        await app.state.redis.ping()
    except Exception as exc:  # приложение должно стартовать и без Redis
        logger.warning("Redis недоступен (%s): %s", settings.redis_url, exc)
    yield
    await app.state.redis.aclose()


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        message = get_message(exc.code, resolve_locale(request), **exc.format_kwargs)
        return _error_response(exc.status_code, exc.code.value, message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = []
        for err in exc.errors():
            loc = [str(part) for part in err.get("loc", ()) if part not in ("body",)]
            details.append(
                ErrorDetail(
                    field=".".join(loc) if loc else None,
                    issue=str(err.get("msg", "invalid")),
                )
            )
        return _error_response(
            400,
            ErrorCode.VALIDATION_ERROR.value,
            get_message(ErrorCode.VALIDATION_ERROR, resolve_locale(request)),
            details,
        )

    @app.exception_handler(ResponseValidationError)
    async def _response_validation_exception_handler(
        request: Request, exc: ResponseValidationError
    ) -> JSONResponse:
        logger.error("Response validation error: %s", exc)
        return _error_response(
            500,
            ErrorCode.INTERNAL_ERROR.value,
            get_message(ErrorCode.INTERNAL_ERROR, resolve_locale(request)),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        mapping: dict[int, ErrorCode] = {
            401: ErrorCode.UNAUTHENTICATED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            405: ErrorCode.METHOD_NOT_ALLOWED,
        }
        code = mapping.get(exc.status_code)
        if code is None:
            # Немаппированный статус: прокидываем деталь как есть.
            return _error_response(
                exc.status_code, ErrorCode.INTERNAL_ERROR.value, str(exc.detail)
            )
        return _error_response(
            exc.status_code, code.value, get_message(code, resolve_locale(request))
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path
        )
        return _error_response(
            500,
            ErrorCode.INTERNAL_ERROR.value,
            get_message(ErrorCode.INTERNAL_ERROR, resolve_locale(request)),
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="REST API системы поддержки принятия решений при проведении ОРМ",
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CSRFMiddleware,
        cookie_name=settings.csrf_cookie_name,
        header_name=settings.csrf_header_name,
        session_cookie_name=settings.session_cookie_name,
        secret_key=settings.secret_key,
        exempt_paths=settings.csrf_exempt_paths,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        max_age=600,
    )

    _register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get(f"{settings.api_v1_prefix}/health", tags=["system"])
    async def health() -> dict[str, Any]:
        return {"data": {"status": "ok"}}

    return app


app = create_app()
