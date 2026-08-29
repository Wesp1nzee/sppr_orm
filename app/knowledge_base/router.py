"""Эндпоинты домена «База знаний»."""

from typing import Annotated

from fastapi import Depends, Query, status

from app.auth.dependencies import CurrentUser, require_roles
from app.auth.models import User, UserRole
from app.core.deps import DbSession
from app.core.pagination import PageParams, get_page_params
from app.core.routing import ApiRouter
from app.core.schemas import DataResponse, PageMeta
from app.knowledge_base.models import NormativeSourceType
from app.knowledge_base.schemas import (
    NormativeDocumentCreate,
    NormativeDocumentListItem,
    NormativeDocumentOut,
    NormativeDocumentSearchParams,
    NormativeDocumentSearchResult,
    NormativeDocumentUpdate,
)
from app.knowledge_base.service import KnowledgeBaseService

router = ApiRouter(prefix="/knowledge-base", tags=["knowledge_base"])

AdminUser = Annotated[User, Depends(require_roles(UserRole.admin))]


@router.get(
    "/documents",
    response_model=DataResponse[list[NormativeDocumentListItem]],
    summary="Список документов базы знаний (текущие версии)",
    responses={401: {"description": "UNAUTHENTICATED — не авторизован"}},
)
async def list_documents(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[PageParams, Depends(get_page_params)],
    source_type: Annotated[
        NormativeSourceType | None, Query(description="Фильтр по типу источника")
    ] = None,
) -> DataResponse[list[NormativeDocumentListItem]]:
    items, total = await KnowledgeBaseService(db).list_documents(
        source_type=source_type, page=page
    )
    return DataResponse[list[NormativeDocumentListItem]](
        data=items,
        meta=PageMeta(page=page.page, per_page=page.per_page, total=total),
    )


@router.get(
    "/documents/search",
    response_model=DataResponse[list[NormativeDocumentSearchResult]],
    summary="Полнотекстовый поиск по документам базы знаний",
    responses={401: {"description": "UNAUTHENTICATED — не авторизован"}},
)
async def search_documents(
    user: CurrentUser,
    db: DbSession,
    params: Annotated[NormativeDocumentSearchParams, Query()],
    page: Annotated[PageParams, Depends(get_page_params)],
) -> DataResponse[list[NormativeDocumentSearchResult]]:
    items, total = await KnowledgeBaseService(db).search_documents(params, page)
    return DataResponse[list[NormativeDocumentSearchResult]](
        data=items,
        meta=PageMeta(page=page.page, per_page=page.per_page, total=total),
    )


@router.get(
    "/documents/{code}",
    response_model=DataResponse[NormativeDocumentOut],
    summary="Текущая версия документа по коду",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        404: {"description": "NORMATIVE_DOCUMENT_NOT_FOUND — документ не найден"},
    },
)
async def get_document(
    code: str,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[NormativeDocumentOut]:
    doc = await KnowledgeBaseService(db).get_by_code(code)
    return DataResponse[NormativeDocumentOut](data=doc)


@router.get(
    "/documents/{code}/history",
    response_model=DataResponse[list[NormativeDocumentOut]],
    summary="История версий документа по коду",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        404: {"description": "NORMATIVE_DOCUMENT_NOT_FOUND — документ не найден"},
    },
)
async def get_history(
    code: str,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[list[NormativeDocumentOut]]:
    history = await KnowledgeBaseService(db).get_history(code)
    return DataResponse[list[NormativeDocumentOut]](data=history)


@router.post(
    "/documents",
    response_model=DataResponse[NormativeDocumentOut],
    status_code=status.HTTP_201_CREATED,
    summary="Создать документ базы знаний (только admin)",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        403: {"description": "INSUFFICIENT_PERMISSIONS — недостаточно прав"},
        409: {
            "description": (
                "NORMATIVE_DOCUMENT_CODE_CONFLICT — документ с таким кодом "
                "уже существует"
            )
        },
    },
)
async def create_document(
    payload: NormativeDocumentCreate,
    admin: AdminUser,
    db: DbSession,
) -> DataResponse[NormativeDocumentOut]:
    doc = await KnowledgeBaseService(db).create_document(admin, payload)
    return DataResponse[NormativeDocumentOut](data=doc)


@router.put(
    "/documents/{code}",
    response_model=DataResponse[NormativeDocumentOut],
    summary="Обновить документ = создать новую версию (только admin)",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        403: {"description": "INSUFFICIENT_PERMISSIONS — недостаточно прав"},
        404: {"description": "NORMATIVE_DOCUMENT_NOT_FOUND — документ не найден"},
    },
)
async def update_document(
    code: str,
    payload: NormativeDocumentUpdate,
    admin: AdminUser,
    db: DbSession,
) -> DataResponse[NormativeDocumentOut]:
    doc = await KnowledgeBaseService(db).update_document(admin, code, payload)
    return DataResponse[NormativeDocumentOut](data=doc)


__all__ = ["router"]
