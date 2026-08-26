"""Роутер домена проверок (ТЗ, раздел 3.1) — заглушка.

Пока пуст и не подключён в ``app/api/v1/router.py`` (см. TODO там).
Подключить после появления эндпоинтов модуля «14 критериев».
"""

from __future__ import annotations

from app.core.routing import ApiRouter

router = ApiRouter(prefix="/checks", tags=["checks"])

__all__ = ["router"]
