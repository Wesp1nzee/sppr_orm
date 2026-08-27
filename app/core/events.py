"""Событийная шина доменных событий: слабая связь между доменами.

Домены-источники (``auth``, ``checks``) публикуют события через ``EventBus``,
не импортируя подписчиков (например, ``audit``). Подписчики регистрируются
в ``lifespan`` приложения и обрабатывают события асинхронно.
"""

import logging
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any, Protocol

logger = logging.getLogger("sppr_orm")


class DomainEvent(Protocol):
    """Маркерный протокол: любое доменное событие."""


EventHandler = Callable[[Any], Awaitable[None]]


class EventBus:
    """Реестр подписчиков, диспетчеризующий события по точному типу."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[EventHandler]] = {}

    def subscribe(self, event_type: type, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                await handler(event)
            except Exception:
                logger.exception("Ошибка обработчика события %s", type(event).__name__)


@lru_cache
def get_event_bus() -> EventBus:
    """Синглтон шины событий (по аналогии с ``get_settings``)."""
    return EventBus()
