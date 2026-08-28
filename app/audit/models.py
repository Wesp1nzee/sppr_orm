"""
Записи журнала аудита неизменяемы (append-only): без ``updated_at``. События
событийной шины фиксируются как строка с типом события, снимком роли
пользователя на момент события и произвольным ``payload`` (JSONB).
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONB, Base


class AuditLogEntry(Base):
    """Одна запись журнала аудита: фиксация события ``EventBus`` в БД.

    ``user_id`` — ``ON DELETE SET NULL``: при удалении пользователя запись
    аудита сохраняется (требование неразрывности журнала). ``user_role`` —
    снимок роли на момент события (не FK — роль могла измениться позже).
    """

    __tablename__ = "audit_log_entries"
    __table_args__ = (Index("ix_audit_log_entries_created_at", "created_at"),)

    updated_at = None  # type: ignore[assignment]

    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLogEntry {self.id} ({self.event_type})>"


__all__ = ["AuditLogEntry"]
