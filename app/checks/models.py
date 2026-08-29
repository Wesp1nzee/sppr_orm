"""Модели данных домена «Проверка по 14 критериям»."""

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import UserRole
from app.db.base import JSONB, Base


class Check(Base):
    """Одна запущенная проверка законности ОРМ."""

    __tablename__ = "checks"
    __table_args__ = (Index("ix_checks_created_at", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role_at_run: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=True), nullable=False
    )
    case_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rules_version: Mapped[str] = mapped_column(String(32), nullable=False)

    results: Mapped[list[CriterionResult]] = relationship(
        back_populates="check",
        cascade="all, delete-orphan",
        order_by="CriterionResult.criterion_number",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Check {self.id} ({self.status})>"


class CriterionResult(Base):
    """Результат одного из 14 критериев в рамках проверки."""

    __tablename__ = "criterion_results"
    __table_args__ = (
        UniqueConstraint(
            "check_id",
            "criterion_number",
            name="uq_criterion_results_check_criterion",
        ),
    )

    check_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checks.id", ondelete="CASCADE"), index=True
    )
    criterion_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    legal_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    recommendations: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    priority_for_role: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    check: Mapped[Check] = relationship(back_populates="results")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CriterionResult {self.criterion_number} ({self.status})>"


__all__ = ["Check", "CriterionResult"]
