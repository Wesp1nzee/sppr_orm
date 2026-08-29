"""Эндпоинты домена «Генерация документов»."""

import uuid
from typing import Annotated, Literal

from fastapi import Depends, Query, Response, status

from app.auth.dependencies import CurrentUser
from app.core.deps import DbSession
from app.core.pagination import PageParams, get_page_params
from app.core.routing import ApiRouter
from app.core.schemas import DataResponse, PageMeta
from app.documents.models import DocumentType
from app.documents.schemas import (
    DocumentContentUpdateRequest,
    DocumentGenerateRequest,
    GeneratedDocumentListItem,
    GeneratedDocumentOut,
)
from app.documents.service import DocumentService

router = ApiRouter(prefix="/documents", tags=["documents"])

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
PDF_MEDIA_TYPE = "application/pdf"


@router.post(
    "",
    response_model=DataResponse[GeneratedDocumentOut],
    status_code=status.HTTP_201_CREATED,
    summary="Генерация документа по результатам проверки",
    responses={
        400: {
            "description": "DOCUMENT_TEMPLATE_MISSING_FIELDS — нет обязательных полей"
        },
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        403: {
            "description": (
                "DOCUMENT_TYPE_NOT_ALLOWED_FOR_ROLE — тип недопустим для роли"
            )
        },
        404: {"description": "CHECK_NOT_FOUND — проверка не найдена"},
    },
)
async def generate_document(
    payload: DocumentGenerateRequest,
    user: CurrentUser,
    db: DbSession,
    check_id: Annotated[uuid.UUID, Query(description="Id проверки (Check)")],
) -> DataResponse[GeneratedDocumentOut]:
    document = await DocumentService(db).generate(
        user, check_id, payload.document_type, payload.extra_fields
    )
    return DataResponse[GeneratedDocumentOut](data=document)


@router.get(
    "",
    response_model=DataResponse[list[GeneratedDocumentListItem]],
    summary="История документов пользователя (admin видит все)",
    responses={401: {"description": "UNAUTHENTICATED — не авторизован"}},
)
async def list_documents(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[PageParams, Depends(get_page_params)],
    check_id: Annotated[uuid.UUID | None, Query()] = None,
    document_type: Annotated[DocumentType | None, Query()] = None,
) -> DataResponse[list[GeneratedDocumentListItem]]:
    items, total = await DocumentService(db).list_for_user(
        user, page, check_id=check_id, document_type=document_type
    )
    return DataResponse[list[GeneratedDocumentListItem]](
        data=items,
        meta=PageMeta(page=page.page, per_page=page.per_page, total=total),
    )


@router.get(
    "/{document_id}",
    response_model=DataResponse[GeneratedDocumentOut],
    summary="Получение документа (владелец или администратор)",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        403: {"description": "FORBIDDEN — документ принадлежит другому пользователю"},
        404: {"description": "DOCUMENT_NOT_FOUND — документ не найден"},
    },
)
async def get_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[GeneratedDocumentOut]:
    document = await DocumentService(db).get_for_user(user, document_id)
    return DataResponse[GeneratedDocumentOut](data=document)


@router.patch(
    "/{document_id}",
    response_model=DataResponse[GeneratedDocumentOut],
    summary="Редактирование содержимого черновика (только владелец)",
    responses={
        400: {"description": "VALIDATION_ERROR — ошибка валидации"},
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        403: {"description": "FORBIDDEN — документ принадлежит другому пользователю"},
        404: {"description": "DOCUMENT_NOT_FOUND — документ не найден"},
        409: {"description": "DOCUMENT_ALREADY_FINALIZED — документ финализирован"},
    },
)
async def update_document(
    document_id: uuid.UUID,
    payload: DocumentContentUpdateRequest,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[GeneratedDocumentOut]:
    document = await DocumentService(db).update_content(user, document_id, payload)
    return DataResponse[GeneratedDocumentOut](data=document)


@router.post(
    "/{document_id}/finalize",
    response_model=DataResponse[GeneratedDocumentOut],
    summary="Финализация черновика",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        403: {"description": "FORBIDDEN — документ принадлежит другому пользователю"},
        404: {"description": "DOCUMENT_NOT_FOUND — документ не найден"},
        409: {"description": "DOCUMENT_ALREADY_FINALIZED — документ финализирован"},
    },
)
async def finalize_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[GeneratedDocumentOut]:
    document = await DocumentService(db).finalize(user, document_id)
    return DataResponse[GeneratedDocumentOut](data=document)


@router.get(
    "/{document_id}/export",
    summary="Экспорт документа в DOCX или PDF",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        403: {"description": "FORBIDDEN — документ принадлежит другому пользователю"},
        404: {"description": "DOCUMENT_NOT_FOUND — документ не найден"},
    },
)
async def export_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    format: Annotated[Literal["docx", "pdf"], Query()] = "docx",
) -> Response:
    content = await DocumentService(db).export(user, document_id, format)
    if format == "pdf":
        media_type = PDF_MEDIA_TYPE
        extension = "pdf"
    else:
        media_type = DOCX_MEDIA_TYPE
        extension = "docx"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="document_{document_id}.{extension}"'
            )
        },
    )


__all__ = ["router"]
