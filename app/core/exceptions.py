"""Domain exceptions and the error-code catalogue from api.md."""

from enum import StrEnum

from app.core.schemas import ErrorDetail


class ErrorCode(StrEnum):
    """Коды ошибок, согласованные в api.md (раздел 1.2)."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    CSRF_TOKEN_INVALID = "CSRF_TOKEN_INVALID"  # noqa: S105 — код ошибки API, не секрет
    RATE_LIMITED = "RATE_LIMITED"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # Специфичные коды домена auth.
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    ADMIN_SELF_REGISTRATION_FORBIDDEN = "ADMIN_SELF_REGISTRATION_FORBIDDEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_CORRUPTED = "SESSION_CORRUPTED"
    USER_NOT_FOUND_OR_INACTIVE = "USER_NOT_FOUND_OR_INACTIVE"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # Специфичные коды домена checks.
    CHECK_NOT_FOUND = "CHECK_NOT_FOUND"

    # Специфичные коды домена knowledge_base.
    NORMATIVE_DOCUMENT_NOT_FOUND = "NORMATIVE_DOCUMENT_NOT_FOUND"
    NORMATIVE_DOCUMENT_CODE_CONFLICT = "NORMATIVE_DOCUMENT_CODE_CONFLICT"

    # Специфичные коды домена documents.
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    DOCUMENT_TYPE_NOT_ALLOWED_FOR_ROLE = "DOCUMENT_TYPE_NOT_ALLOWED_FOR_ROLE"
    DOCUMENT_ALREADY_FINALIZED = "DOCUMENT_ALREADY_FINALIZED"
    DOCUMENT_TEMPLATE_MISSING_FIELDS = "DOCUMENT_TEMPLATE_MISSING_FIELDS"

    # Специфичные коды домена audit.
    AUDIT_LOG_ENTRY_NOT_FOUND = "AUDIT_LOG_ENTRY_NOT_FOUND"

    # Специфичные коды домена case_materials.
    CASE_MATERIAL_NOT_FOUND = "CASE_MATERIAL_NOT_FOUND"
    CASE_MATERIAL_FILE_TOO_LARGE = "CASE_MATERIAL_FILE_TOO_LARGE"
    CASE_MATERIAL_UNSUPPORTED_FORMAT = "CASE_MATERIAL_UNSUPPORTED_FORMAT"
    CASE_MATERIAL_NOT_READY = "CASE_MATERIAL_NOT_READY"


#: HTTP-статус по умолчанию для каждого кода.
_DEFAULT_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.CSRF_TOKEN_INVALID: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.EMAIL_ALREADY_REGISTERED: 409,
    ErrorCode.ADMIN_SELF_REGISTRATION_FORBIDDEN: 403,
    ErrorCode.INVALID_CREDENTIALS: 401,
    ErrorCode.ACCOUNT_DEACTIVATED: 403,
    ErrorCode.SESSION_NOT_FOUND: 401,
    ErrorCode.SESSION_CORRUPTED: 401,
    ErrorCode.USER_NOT_FOUND_OR_INACTIVE: 401,
    ErrorCode.INSUFFICIENT_PERMISSIONS: 403,
    ErrorCode.CHECK_NOT_FOUND: 404,
    ErrorCode.NORMATIVE_DOCUMENT_NOT_FOUND: 404,
    ErrorCode.NORMATIVE_DOCUMENT_CODE_CONFLICT: 409,
    ErrorCode.DOCUMENT_NOT_FOUND: 404,
    ErrorCode.DOCUMENT_TYPE_NOT_ALLOWED_FOR_ROLE: 403,
    ErrorCode.DOCUMENT_ALREADY_FINALIZED: 409,
    ErrorCode.DOCUMENT_TEMPLATE_MISSING_FIELDS: 400,
    ErrorCode.AUDIT_LOG_ENTRY_NOT_FOUND: 404,
    ErrorCode.CASE_MATERIAL_NOT_FOUND: 404,
    ErrorCode.CASE_MATERIAL_FILE_TOO_LARGE: 400,
    ErrorCode.CASE_MATERIAL_UNSUPPORTED_FORMAT: 400,
    ErrorCode.CASE_MATERIAL_NOT_READY: 409,
}


class AppException(Exception):
    """Бизнес-исключение: ErrorCode + параметры подстановки в шаблон.

    Текст сообщения не хранится в исключении — он резолвится в exception
    handler'е (``app/main.py``) по коду и локали запроса (см.
    ``app/core/messages.py``). ``format_kwargs`` подставляются в шаблон
    через ``str.format``.

    Перехватывается глобальным handler'ом и сериализуется в единый формат
    ``{"error": {...}}`` из api.md.
    """

    def __init__(
        self,
        code: ErrorCode,
        status_code: int | None = None,
        details: list[ErrorDetail] | None = None,
        **format_kwargs: str,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.status_code = (
            status_code if status_code is not None else _DEFAULT_STATUS[code]
        )
        self.details = details or []
        self.format_kwargs = format_kwargs

    # --- Фабрики типовых ошибок ------------------------------------------

    @staticmethod
    def _build(code: ErrorCode, format_kwargs: dict[str, str]) -> AppException:
        exc = AppException(code)
        exc.format_kwargs.update(format_kwargs)
        return exc

    @classmethod
    def not_found(cls, **format_kwargs: str) -> AppException:
        return cls._build(ErrorCode.NOT_FOUND, format_kwargs)

    @classmethod
    def conflict(cls, **format_kwargs: str) -> AppException:
        return cls._build(ErrorCode.CONFLICT, format_kwargs)

    @classmethod
    def unauthenticated(cls, **format_kwargs: str) -> AppException:
        return cls._build(ErrorCode.UNAUTHENTICATED, format_kwargs)

    @classmethod
    def forbidden(cls, **format_kwargs: str) -> AppException:
        return cls._build(ErrorCode.FORBIDDEN, format_kwargs)

    @classmethod
    def rate_limited(cls, **format_kwargs: str) -> AppException:
        return cls._build(ErrorCode.RATE_LIMITED, format_kwargs)
