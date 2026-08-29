"""Домен «Логирование/аудит».

События ``EventBus`` из доменов-источников сохраняются в ``audit_log_entries``;
API просмотра журнала и сводного отчёта — в ``app/audit/router.py``. Подписчики
регистрируются в ``lifespan`` приложения (``app/main.py``).
"""

from app.audit.subscribers import setup_audit_subscribers

__all__ = ["setup_audit_subscribers"]
