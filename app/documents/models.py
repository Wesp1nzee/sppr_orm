"""Модели данных домена «Генерация документов»."""

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONB, Base


class DocumentType(StrEnum):
    """Типы процессуальных документов"""

    exclusion_motion = "exclusion_motion"  # ходатайство об исключении доказательств
    court_decision_copy_request = (
        "court_decision_copy_request"  # истребование копии судебного решения
    )
    data_request_complaint = "data_request_complaint"  # жалоба по ч. 4 ст. 5 ФЗ об ОРД
    officer_checklist = (
        "officer_checklist"  # чек-лист следователя/оперативного сотрудника
    )
    legalization_plan = "legalization_plan"  # план процессуальной легализации


class DocumentStatus(StrEnum):
    """Жизненный цикл документа: черновик → финализированный."""

    draft = "draft"
    finalized = "finalized"


class GeneratedDocument(Base):
    """Сгенерированный документ: структурированное содержимое в ``content``.

    Документ хранится как редактируемая сущность (JSONB-содержимое по разделам
    шаблона), а не как готовый файл — экспорт в DOCX/PDF выполняется на лету из
    финализированного содержимого.
    """

    __tablename__ = "generated_documents"
    __table_args__ = (Index("ix_generated_documents_created_at", "created_at"),)

    check_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checks.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type", native_enum=True),
        nullable=False,
        index=True,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status", native_enum=True),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GeneratedDocument {self.id} ({self.document_type.value})>"


__all__ = ["DocumentStatus", "DocumentType", "GeneratedDocument"]
