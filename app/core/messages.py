"""Каталог сообщений об ошибках (раздел ТЗ «Локализация»).

Каждому ``ErrorCode`` соответствует перевод на поддерживаемые языки
(сейчас ru/en). Обработчики исключений резолвят текст по коду + локали,
определяемой из заголовка ``Accept-Language`` запроса (по умолчанию
«ru»). Полноценный gettext/babel на этом этапе не нужен: простой словарь
+ fallback. Чтобы добавить язык, достаточно дополнить словарь —
код приложения менять не требуется.
"""

from starlette.requests import Request

from app.core.exceptions import ErrorCode

DEFAULT_LOCALE = "ru"
SUPPORTED_LOCALES: frozenset[str] = frozenset({"ru", "en"})

MESSAGES: dict[ErrorCode, dict[str, str]] = {
    ErrorCode.VALIDATION_ERROR: {
        "ru": "Ошибка валидации запроса",
        "en": "Request validation error",
    },
    ErrorCode.UNAUTHENTICATED: {
        "ru": "Не авторизован",
        "en": "Not authenticated",
    },
    ErrorCode.FORBIDDEN: {
        "ru": "Доступ запрещён",
        "en": "Access denied",
    },
    ErrorCode.NOT_FOUND: {
        "ru": "Ресурс не найден",
        "en": "Resource not found",
    },
    ErrorCode.CONFLICT: {
        "ru": "Конфликт данных",
        "en": "Data conflict",
    },
    ErrorCode.CSRF_TOKEN_INVALID: {
        "ru": "Неверный или отсутствующий CSRF-токен",
        "en": "Invalid or missing CSRF token",
    },
    ErrorCode.RATE_LIMITED: {
        "ru": "Слишком много запросов, попробуйте позже",
        "en": "Too many requests, try again later",
    },
    ErrorCode.METHOD_NOT_ALLOWED: {
        "ru": "Метод не поддерживается",
        "en": "Method not allowed",
    },
    ErrorCode.INTERNAL_ERROR: {
        "ru": "Внутренняя ошибка сервера",
        "en": "Internal server error",
    },
    ErrorCode.EMAIL_ALREADY_REGISTERED: {
        "ru": "Пользователь с таким email уже зарегистрирован",
        "en": "A user with this email is already registered",
    },
    ErrorCode.ADMIN_SELF_REGISTRATION_FORBIDDEN: {
        "ru": "Самостоятельная регистрация администратора запрещена",
        "en": "Self-registration as administrator is forbidden",
    },
    ErrorCode.INVALID_CREDENTIALS: {
        "ru": "Неверный email или пароль",
        "en": "Invalid email or password",
    },
    ErrorCode.ACCOUNT_DEACTIVATED: {
        "ru": "Учётная запись деактивирована",
        "en": "Account is deactivated",
    },
    ErrorCode.SESSION_NOT_FOUND: {
        "ru": "Сессия не найдена или истекла, выполните вход",
        "en": "Session not found or expired, please sign in",
    },
    ErrorCode.SESSION_CORRUPTED: {
        "ru": "Сессия повреждена, выполните вход",
        "en": "Session is corrupted, please sign in",
    },
    ErrorCode.USER_NOT_FOUND_OR_INACTIVE: {
        "ru": "Пользователь не найден или деактивирован",
        "en": "User not found or deactivated",
    },
    ErrorCode.INSUFFICIENT_PERMISSIONS: {
        "ru": "Недостаточно прав для выполнения операции",
        "en": "Insufficient permissions for this operation",
    },
    ErrorCode.CHECK_NOT_FOUND: {
        "ru": "Проверка не найдена",
        "en": "Check not found",
    },
    ErrorCode.NORMATIVE_DOCUMENT_NOT_FOUND: {
        "ru": "Документ базы знаний не найден",
        "en": "Knowledge base document not found",
    },
    ErrorCode.NORMATIVE_DOCUMENT_CODE_CONFLICT: {
        "ru": "Документ с таким кодом уже существует",
        "en": "A document with this code already exists",
    },
    ErrorCode.DOCUMENT_NOT_FOUND: {
        "ru": "Документ не найден",
        "en": "Document not found",
    },
    ErrorCode.DOCUMENT_TYPE_NOT_ALLOWED_FOR_ROLE: {
        "ru": "Данный тип документа недоступен для вашей роли",
        "en": "This document type is not allowed for your role",
    },
    ErrorCode.DOCUMENT_ALREADY_FINALIZED: {
        "ru": "Документ уже финализирован и недоступен для редактирования",
        "en": "The document is already finalized and cannot be edited",
    },
    ErrorCode.DOCUMENT_TEMPLATE_MISSING_FIELDS: {
        "ru": "Не заполнены обязательные поля шаблона: {fields}",
        "en": "Required template fields are missing: {fields}",
    },
    ErrorCode.AUDIT_LOG_ENTRY_NOT_FOUND: {
        "ru": "Запись журнала аудита не найдена",
        "en": "Audit log entry not found",
    },
}


def get_message(
    code: ErrorCode, locale: str | None = None, **format_kwargs: str
) -> str:
    """Возвращает текст сообщения для ``ErrorCode`` в заданной локали.

    Неподдерживаемая локаль или отсутствующий перевод → fallback на
    ``DEFAULT_LOCALE``. ``format_kwargs`` подставляются в шаблон через
    ``str.format``; при несовпадении ключей возвращается исходный шаблон.
    """
    translations = MESSAGES.get(code)
    if translations is None:
        return code.value
    template = translations.get(locale or DEFAULT_LOCALE) or translations.get(
        DEFAULT_LOCALE, code.value
    )
    if format_kwargs:
        try:
            return template.format(**format_kwargs)
        except (KeyError, IndexError, ValueError):  # fmt: skip
            return template
    return template


def resolve_locale(request: Request) -> str:
    """Определяет локаль из заголовка ``Accept-Language``.

    Берётся первый поддерживаемый язык; иначе — ``DEFAULT_LOCALE`` («ru»).
    """
    accept_language = request.headers.get("accept-language", "")
    for part in accept_language.split(","):
        lang = part.split(";")[0].strip().lower()
        if lang in SUPPORTED_LOCALES:
            return lang
    return DEFAULT_LOCALE
