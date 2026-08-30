"""Эндпоинты домена «Импорт материалов дела»."""

import uuid
from typing import Annotated

from fastapi import Depends, File, UploadFile, status

from app.auth.dependencies import CurrentUser
from app.case_materials.schemas import (
    CaseMaterialConfirmRequest,
    CaseMaterialDetailOut,
    CaseMaterialListItem,
    CaseMaterialUploadOut,
)
from app.case_materials.service import CaseMaterialService
from app.checks.schemas import CheckOut
from app.core.deps import DbSession
from app.core.pagination import PageParams, get_page_params
from app.core.routing import ApiRouter
from app.core.schemas import DataResponse, PageMeta

router = ApiRouter(prefix="/case-materials", tags=["case_materials"])


@router.post(
    "",
    response_model=DataResponse[CaseMaterialUploadOut],
    status_code=status.HTTP_201_CREATED,
    summary="Загрузка материалов дела (PDF/DOCX) с извлечением текста",
    responses={
        400: {
            "description": (
                "CASE_MATERIAL_UNSUPPORTED_FORMAT / CASE_MATERIAL_FILE_TOO_LARGE"
            )
        },
        401: {"description": "UNAUTHENTICATED — не авторизован"},
    },
)
async def upload_case_material(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File(description="Файл PDF или DOCX")],
) -> DataResponse[CaseMaterialUploadOut]:
    material = await CaseMaterialService(db).upload(user, file)
    return DataResponse[CaseMaterialUploadOut](data=material)


@router.get(
    "",
    response_model=DataResponse[list[CaseMaterialListItem]],
    summary="Список загрузок материалов (свои — для пользователя, все — для admin)",
    responses={401: {"description": "UNAUTHENTICATED — не авторизован"}},
)
async def list_case_materials(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[PageParams, Depends(get_page_params)],
) -> DataResponse[list[CaseMaterialListItem]]:
    items, total = await CaseMaterialService(db).list_for_user(user, page)
    return DataResponse[list[CaseMaterialListItem]](
        data=items,
        meta=PageMeta(page=page.page, per_page=page.per_page, total=total),
    )


@router.get(
    "/{upload_id}",
    response_model=DataResponse[CaseMaterialDetailOut],
    summary="Детали материала дела (владелец или администратор)",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        404: {"description": "CASE_MATERIAL_NOT_FOUND — материал не найден"},
    },
)
async def get_case_material(
    upload_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[CaseMaterialDetailOut]:
    material = await CaseMaterialService(db).get_for_user(user, upload_id)
    return DataResponse[CaseMaterialDetailOut](data=material)


@router.post(
    "/{upload_id}/confirm",
    response_model=DataResponse[CheckOut],
    status_code=status.HTTP_201_CREATED,
    summary="Подтверждение черновика и создание проверки",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        404: {"description": "CASE_MATERIAL_NOT_FOUND — материал не найден"},
        409: {"description": "CASE_MATERIAL_NOT_READY — извлечение не завершено"},
    },
)
async def confirm_case_material(
    upload_id: uuid.UUID,
    payload: CaseMaterialConfirmRequest,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[CheckOut]:
    check = await CaseMaterialService(db).confirm(user, upload_id, payload)
    return DataResponse[CheckOut](data=check)


__all__ = ["router"]
