"""Домен «Логирование/аудит» (ТЗ, раздел 3.5).

Полноценная audit-таблица не входит в текущую задачу. Здесь — заготовка
подписчика на ``EventBus``: события из ``auth`` и ``checks`` логируются,
но не пишутся в БД. Связь между доменами — только через ``EventBus`` и типы
событий, объявленные в доменах-источниках.
"""

from __future__ import annotations

import logging
from typing import Any

from app.auth.service import UserLoggedIn, UserLoggedOut, UserRegistered
from app.checks.service import CheckCreated
from app.core.events import EventBus

logger = logging.getLogger("sppr_orm.audit")


async def _log_event(event: Any) -> None:
    logger.info("audit event: %r", event)


def setup_audit_subscribers(bus: EventBus) -> None:
    """Регистрирует заглушки обработчиков событий (без записи в БД)."""
    bus.subscribe(UserRegistered, _log_event)
    bus.subscribe(UserLoggedIn, _log_event)
    bus.subscribe(UserLoggedOut, _log_event)
    bus.subscribe(CheckCreated, _log_event)
