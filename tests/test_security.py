"""Тесты хэширования паролей: Argon2id (новая схема) + legacy-bcrypt."""

from __future__ import annotations

from app.core.security import hash_password, verify_password

# bcrypt-хэш пароля "legacy-password" (формат passlib 1.7.4, bcrypt 4.0.1) —
# имитирует хэши, которые могли остаться в БД до миграции на pwdlib.
LEGACY_BCRYPT_HASH = "$2b$12$nxVECmtGFVv7pdYJRQyEiuTSI2r/30/a0qsaSd8ICW31H56obCuKG"


def test_hash_password_uses_argon2id() -> None:
    hashed = hash_password("secret-password")
    assert hashed.startswith("$argon2id$")
    assert hashed != "secret-password"


def test_verify_argon2id_hash() -> None:
    hashed = hash_password("secret-password")
    assert verify_password("secret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_verify_legacy_bcrypt_hash() -> None:
    assert verify_password("legacy-password", LEGACY_BCRYPT_HASH)
    assert not verify_password("wrong-password", LEGACY_BCRYPT_HASH)


def test_verify_malformed_hash_returns_false() -> None:
    assert not verify_password("anything", "not-a-hash")
    assert not verify_password("anything", "")
