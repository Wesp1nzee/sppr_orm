"""Бизнес-логика домена «Импорт материалов дела»."""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User, UserRole
from app.case_materials.constants import (
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_BYTES,
    MIN_TEXT_CHARS_PER_PAGE,
    TEXT_EXTRACTION_FAILED_MESSAGE,
    CaseMaterialStatus,
)
from app.case_materials.extraction import (
    DetectedDocument,
    DocumentSegmenter,
    ExtractedText,
    extractor_for,
)
from app.case_materials.fields import FIELD_EXTRACTORS
from app.case_materials.models import CaseMaterialUpload
from app.case_materials.repository import (
    CaseMaterialRepository,
    CaseMaterialRepositoryProtocol,
)
from app.case_materials.schemas import (
    CaseMaterialConfirmRequest,
    CaseMaterialDetailOut,
    CaseMaterialListItem,
    CaseMaterialUploadOut,
    DetectedDocumentOut,
    ExtractedFieldOut,
)
from app.checks.schemas import CheckCreateRequest, CheckOut
from app.checks.service import CheckService
from app.core.config import get_settings
from app.core.events import EventBus, get_event_bus
from app.core.exceptions import AppException, ErrorCode
from app.core.pagination import PageParams

logger = logging.getLogger("sppr_orm.case_materials")


@dataclass(frozen=True)
class CaseMaterialUploaded:
    """Событие: загружен файл материалов дела (для подписчиков, напр. ``audit``)."""

    upload_id: uuid.UUID
    user_id: uuid.UUID


class CaseMaterialService:
    def __init__(
        self,
        session: AsyncSession,
        repo: CaseMaterialRepositoryProtocol | None = None,
        checks: CheckService | None = None,
        events: EventBus | None = None,
        storage_dir: Path | None = None,
    ) -> None:
        self._session = session
        self._repo = repo or CaseMaterialRepository(session)
        self._checks = checks or CheckService(session)
        self._events = events or get_event_bus()
        self._storage_dir = Path(
            storage_dir or get_settings().case_materials_storage_dir
        )

    async def upload(self, user: User, file: UploadFile) -> CaseMaterialUploadOut:
        """Валидирует, сохраняет файл, извлекает текст и сегментирует документы."""
        mime_type = (file.content_type or "").strip().lower()
        if mime_type not in ALLOWED_MIME_TYPES:
            raise AppException(ErrorCode.CASE_MATERIAL_UNSUPPORTED_FORMAT)

        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise AppException(ErrorCode.CASE_MATERIAL_FILE_TOO_LARGE)
        if not data:
            raise AppException(ErrorCode.CASE_MATERIAL_UNSUPPORTED_FORMAT)

        storage_path = self._save_file(data, file.filename or "upload")
        material = CaseMaterialUpload(
            user_id=user.id,
            original_filename=file.filename or "upload",
            mime_type=mime_type,
            file_size_bytes=len(data),
            storage_path=storage_path,
            content_hash=hashlib.sha256(data).hexdigest(),
            status=CaseMaterialStatus.processing,
        )
        await self._repo.add(material)

        extracted = self._try_extract(mime_type, data, file.filename or "")
        if extracted is None:
            material.status = CaseMaterialStatus.failed
            material.error_message = TEXT_EXTRACTION_FAILED_MESSAGE
        elif _is_text_too_sparse(extracted):
            material.status = CaseMaterialStatus.text_extraction_failed
            material.error_message = TEXT_EXTRACTION_FAILED_MESSAGE
        else:
            documents = DocumentSegmenter().segment(extracted)
            material.extracted_text = extracted.text
            material.detected_documents = [_serialize_document(d) for d in documents]
            material.suggested_check_answers = _merge_answers(documents) or None
            material.status = CaseMaterialStatus.extracted

        await self._events.publish(
            CaseMaterialUploaded(upload_id=material.id, user_id=user.id)
        )
        return self._to_out(material)

    async def get_for_user(
        self, user: User, upload_id: uuid.UUID
    ) -> CaseMaterialDetailOut:
        material = await self._require_owned(user, upload_id)
        return self._to_detail(material)

    async def list_for_user(
        self, user: User, page: PageParams
    ) -> tuple[list[CaseMaterialListItem], int]:
        user_id = None if user.role is UserRole.admin else user.id
        materials = await self._repo.list_for_user(
            user_id=user_id, page=page.page, per_page=page.per_page, sort=page.sort
        )
        total = await self._repo.count(user_id=user_id)
        return [self._to_list_item(m) for m in materials], total

    async def build_check_draft(
        self, user: User, upload_id: uuid.UUID
    ) -> dict[str, Any]:
        """Черновик для экрана подтверждения: ответы + несопоставленные документы."""
        material = await self._require_owned(user, upload_id)
        priority = {kind.value for kind in FIELD_EXTRACTORS}
        text = material.extracted_text or ""
        unmatched: list[dict[str, Any]] = []
        for doc in material.detected_documents:
            if doc.get("document_type") in priority:
                continue
            start = int(doc.get("start", 0))
            end = int(doc.get("end", len(text)))
            unmatched.append(
                {
                    "document_type": doc["document_type"],
                    "title": doc["title"],
                    "text": text[start:end],
                }
            )
        return {
            "answers": material.suggested_check_answers or {},
            "unmatched_documents": unmatched,
        }

    async def confirm(
        self, user: User, upload_id: uuid.UUID, payload: CaseMaterialConfirmRequest
    ) -> CheckOut:
        """Создаёт проверку по подтверждённому черновику (явное действие)."""
        material = await self._require_owned(user, upload_id)
        if material.status is not CaseMaterialStatus.extracted:
            raise AppException(ErrorCode.CASE_MATERIAL_NOT_READY)
        return await self._checks.create(
            user,
            CheckCreateRequest(case_title=payload.case_title, answers=payload.answers),
        )

    async def _require_owned(
        self, user: User, upload_id: uuid.UUID
    ) -> CaseMaterialUpload:
        material = await self._repo.get_by_id(upload_id)
        if material is None or (
            material.user_id != user.id and user.role is not UserRole.admin
        ):
            raise AppException(ErrorCode.CASE_MATERIAL_NOT_FOUND)
        return material

    def _save_file(self, data: bytes, original_filename: str) -> str:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(original_filename).suffix.lower() or ".bin"
        name = f"{uuid.uuid4().hex}{suffix}"
        (self._storage_dir / name).write_bytes(data)
        return name

    @staticmethod
    def _try_extract(
        mime_type: str, data: bytes, filename: str
    ) -> ExtractedText | None:
        try:
            return extractor_for(mime_type).extract(data, filename)
        except Exception:
            logger.exception("Не удалось извлечь текст из %s", filename)
            return None

    def _to_list_item(self, material: CaseMaterialUpload) -> CaseMaterialListItem:
        return CaseMaterialListItem(
            id=material.id,
            status=material.status,
            original_filename=material.original_filename,
            mime_type=material.mime_type,
            file_size_bytes=material.file_size_bytes,
            created_at=material.created_at,
        )

    def _to_out(self, material: CaseMaterialUpload) -> CaseMaterialUploadOut:
        return CaseMaterialUploadOut(
            id=material.id,
            status=material.status,
            original_filename=material.original_filename,
            mime_type=material.mime_type,
            file_size_bytes=material.file_size_bytes,
            created_at=material.created_at,
            detected_documents=self._documents_out(material),
            suggested_check_answers=material.suggested_check_answers,
            error_message=material.error_message,
        )

    def _to_detail(self, material: CaseMaterialUpload) -> CaseMaterialDetailOut:
        return CaseMaterialDetailOut(
            id=material.id,
            status=material.status,
            original_filename=material.original_filename,
            mime_type=material.mime_type,
            file_size_bytes=material.file_size_bytes,
            created_at=material.created_at,
            detected_documents=self._documents_out(material),
            suggested_check_answers=material.suggested_check_answers,
            error_message=material.error_message,
        )

    @staticmethod
    def _documents_out(material: CaseMaterialUpload) -> list[DetectedDocumentOut]:
        text = material.extracted_text or ""
        documents: list[DetectedDocumentOut] = []
        for doc in material.detected_documents:
            start = int(doc.get("start", 0))
            end = int(doc.get("end", len(text)))
            documents.append(
                DetectedDocumentOut(
                    document_type=doc["document_type"],
                    title=doc["title"],
                    page=doc.get("page"),
                    fields={
                        name: ExtractedFieldOut(**value)
                        for name, value in doc.get("fields", {}).items()
                    },
                    text=text[start:end],
                )
            )
        return documents


def _is_text_too_sparse(extracted: ExtractedText) -> bool:
    if not extracted.text.strip():
        return True
    pages = extracted.pages or [extracted.text]
    return len(extracted.text) / len(pages) < MIN_TEXT_CHARS_PER_PAGE


def _serialize_document(document: DetectedDocument) -> dict[str, Any]:
    return {
        "document_type": document.kind.value,
        "title": document.title,
        "page": document.page,
        "start": document.start,
        "end": document.end,
        "fields": {
            name: {"value": field.value, "confidence": field.confidence}
            for name, field in document.fields.items()
        },
    }


def _merge_answers(documents: list[DetectedDocument]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for document in documents:
        for criterion, fields in document.suggested_answers.items():
            merged.setdefault(criterion, {}).update(fields)
    return merged


__all__ = ["CaseMaterialService", "CaseMaterialUploaded"]
