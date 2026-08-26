"""Domain exceptions and the error-code catalogue from api.md."""

from __future__ import annotations

import enum

from app.schemas.common import ErrorDetail


class ErrorCode(str, enum.Enum):
    """Коды ошибок, согласованные в api.md (раздел 1.2)."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    CSRF_TOKEN_INVALID = "CSRF_TOKEN_INVALID"
    RATE_LIMITED = "RATE_LIMITED"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppException(Exception):
    """Бизнес-исключение с кодом, статусом и деталями.

    Перехватывается глобальным handler'ом в ``app/main.py`` и сериализуется
    в единый формат ``{"error": {...}}`` из api.md.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []

    # --- Фабрики типовых ошибок ------------------------------------------

    @classmethod
    def not_found(cls, message: str = "Ресурс не найден") -> AppException:
        return cls(ErrorCode.NOT_FOUND, message, 404)

    @classmethod
    def conflict(cls, message: str) -> AppException:
        return cls(ErrorCode.CONFLICT, message, 409)

    @classmethod
    def unauthenticated(cls, message: str = "Не авторизован") -> AppException:
        return cls(ErrorCode.UNAUTHENTICATED, message, 401)

    @classmethod
    def forbidden(cls, message: str = "Недостаточно прав") -> AppException:
        return cls(ErrorCode.FORBIDDEN, message, 403)

    @classmethod
    def rate_limited(cls, message: str = "Слишком много запросов, попробуйте позже") -> AppException:
        return cls(ErrorCode.RATE_LIMITED, message, 429)
