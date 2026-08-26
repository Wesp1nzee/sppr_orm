"""Pydantic-схемы модуля аутентификации (api.md, раздел 2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.config import get_settings
from app.models.user import UserRole

_settings = get_settings()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=_settings.password_min_length,
        max_length=_settings.password_max_length,
        description="Пароль пользователя",
    )
    full_name: str = Field(min_length=2, max_length=255, description="ФИО")
    role: UserRole = Field(default=UserRole.lawyer, description="Роль пользователя")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=_settings.password_max_length)


class UserOut(BaseModel):
    """Публичное представление пользователя (без хэша пароля)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class LoginData(BaseModel):
    """Тело ответа на логин (api.md: id, role, full_name + csrf для SPA)."""

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    full_name: str
    csrf_token: str


class CsrfData(BaseModel):
    csrf_token: str


class LogoutData(BaseModel):
    success: bool = True
