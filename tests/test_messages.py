"""Тесты каталога сообщений и резолва локали."""

from app.core.exceptions import ErrorCode
from app.core.messages import DEFAULT_LOCALE, get_message


def test_get_message_ru_default() -> None:
    assert get_message(ErrorCode.SESSION_NOT_FOUND) == (
        "Сессия не найдена или истекла, выполните вход"
    )


def test_get_message_en() -> None:
    assert get_message(ErrorCode.SESSION_NOT_FOUND, "en") == (
        "Session not found or expired, please sign in"
    )


def test_get_message_unsupported_locale_falls_back_to_ru() -> None:
    assert get_message(ErrorCode.SESSION_NOT_FOUND, "de") == (
        "Сессия не найдена или истекла, выполните вход"
    )


def test_get_message_unknown_code_returns_code_value() -> None:
    class FakeCode(str):
        value = "FAKE"

    assert get_message(FakeCode()) == "FAKE"  # type: ignore[arg-type]


def test_every_error_code_has_ru_translation() -> None:
    for code in ErrorCode:
        assert get_message(code, DEFAULT_LOCALE)
        assert get_message(code, "en")
