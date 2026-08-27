"""Модели данных домена «База знаний» (ТЗ, раздел 3.3)."""

import uuid
from enum import StrEnum
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONB, Base


class NormativeSourceType(StrEnum):
    """Тип материала базы знаний."""

    federal_law = "federal_law"  # ФЗ «Об ОРД», статьи УПК РФ
    ks_rf_ruling = "ks_rf_ruling"  # определения Конституционного Суда РФ
    plenum_resolution = "plenum_resolution"  # постановления Пленума ВС РФ
    expert_comment = "expert_comment"  # комментарии юристов-экспертов


class NormativeDocument(Base):
    """Нормативный материал базы знаний (закон, определение КС, Пленум, комментарий).

    Все типы живут в одной таблице: общий набор полей + специфичные метаданные
    в ``extra`` (JSONB). Обновление документа создаёт новую версию (строку с тем
    же ``code`` и увеличенным ``version``), а не переписывает существующую.
    """

    __tablename__ = "normative_documents"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_normdoc_code_version"),
        Index("ix_normdoc_code_is_current", "code", "is_current"),
    )

    source_type: Mapped[NormativeSourceType] = mapped_column(
        SAEnum(NormativeSourceType, name="normative_source_type", native_enum=True),
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    full_text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NormativeDocument {self.code} v{self.version}>"


__all__ = ["NormativeDocument", "NormativeSourceType"]
