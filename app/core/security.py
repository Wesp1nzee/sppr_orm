"""Криптографические примитивы: хэширование паролей, генерация токенов.

Пароли: Argon2id (pwdlib) для новых хэшей; bcrypt оставлен как legacy-схема
для верификации старых хэшей в БД (до их перехэширования при следующем входе).
"""

from __future__ import annotations

import secrets

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

# Argon2id — основная схема; bcrypt — верификация legacy-хэшей.
_password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def hash_password(password: str) -> str:
    """Возвращает Argon2id-хэш пароля."""
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль против хэша (Argon2id или legacy-bcrypt).

    Возвращает False при неверном пароле или нераспознанном/битом хэше.
    """
    try:
        return _password_hash.verify(plain_password, hashed_password)
    except (TypeError, ValueError, UnknownHashError):  # fmt: skip
        return False


def generate_token(nbytes: int = 32) -> str:
    """Криптографически стойкий случайный токен (URL-safe, base64)."""
    return secrets.token_urlsafe(nbytes)


def constant_time_equals(a: str, b: str) -> bool:
    """Сравнение за константное время (для CSRF и прочих токенов)."""
    return secrets.compare_digest(a, b)
