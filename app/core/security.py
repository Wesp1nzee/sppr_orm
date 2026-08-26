"""Криптографические примитивы: хэширование паролей, генерация токенов."""

from __future__ import annotations

import secrets

from passlib.context import CryptContext  # type: ignore[import-untyped]

# bcrypt (пин 4.0.1 — см. pyproject: совместимость passlib 1.7.4 с bcrypt>=4.1)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Возвращает bcrypt-хэш пароля."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль против хэша. Возвращает False при неверном/битом хэше."""
    try:
        return _pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


def generate_token(nbytes: int = 32) -> str:
    """Криптографически стойкий случайный токен (URL-safe, base64)."""
    return secrets.token_urlsafe(nbytes)


def constant_time_equals(a: str, b: str) -> bool:
    """Сравнение за константное время (для CSRF и прочих токенов)."""
    return secrets.compare_digest(a, b)
