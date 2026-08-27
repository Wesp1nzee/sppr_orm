"""Эндпоинты домена «Проверки» (ТЗ, раздел 7)."""

import uuid
from typing import Annotated

from fastapi import Depends, status

from app.auth.dependencies import CurrentUser
from app.checks.schemas import CheckCreateRequest, CheckListItem, CheckOut
from app.checks.service import CheckService
from app.core.deps import DbSession
from app.core.pagination import PageParams, get_page_params
from app.core.routing import ApiRouter
from app.core.schemas import DataResponse, PageMeta

router = ApiRouter(prefix="/checks", tags=["checks"])


@router.post(
    "",
    response_model=DataResponse[CheckOut],
    status_code=status.HTTP_201_CREATED,
    summary="Запуск проверки законности ОРМ по 14 критериям",
    responses={
        400: {"description": "VALIDATION_ERROR — ошибка валидации запроса"},
        401: {"description": "UNAUTHENTICATED — не авторизован"},
    },
)
async def create_check(
    payload: CheckCreateRequest,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[CheckOut]:
    check = await CheckService(db).create(user, payload)
    return DataResponse[CheckOut](data=check)


@router.get(
    "/{check_id}",
    response_model=DataResponse[CheckOut],
    summary="Получение проверки по id (владелец или администратор)",
    responses={
        401: {"description": "UNAUTHENTICATED — не авторизован"},
        404: {"description": "CHECK_NOT_FOUND — проверка не найдена"},
    },
)
async def get_check(
    check_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> DataResponse[CheckOut]:
    check = await CheckService(db).get_for_user(user, check_id)
    return DataResponse[CheckOut](data=check)


@router.get(
    "",
    response_model=DataResponse[list[CheckListItem]],
    summary="Список проверок (свои — для пользователя, все — для администратора)",
    responses={401: {"description": "UNAUTHENTICATED — не авторизован"}},
)
async def list_checks(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[PageParams, Depends(get_page_params)],
) -> DataResponse[list[CheckListItem]]:
    items, total = await CheckService(db).list_for_user(user, page)
    return DataResponse[list[CheckListItem]](
        data=items,
        meta=PageMeta(page=page.page, per_page=page.per_page, total=total),
    )


__all__ = ["router"]
