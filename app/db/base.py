"""Declarative base with common columns for every table."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSONB = JSON().with_variant(PGJSONB, "postgresql")


class Base(DeclarativeBase):
    """Общий базовый класс: UUID PK + служебные timestamp'ы."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
