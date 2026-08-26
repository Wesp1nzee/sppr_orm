"""Параметры пагинации из query-string (api.md, раздел 1.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Query

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


@dataclass(frozen=True)
class PageParams:
    page: int = 1
    per_page: int = DEFAULT_PER_PAGE
    sort: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


async def get_page_params(
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    per_page: Annotated[
        int, Query(ge=1, le=MAX_PER_PAGE, description="Записей на странице")
    ] = DEFAULT_PER_PAGE,
    sort: Annotated[
        str | None, Query(description='Сортировка, напр. "-created_at"')
    ] = None,
) -> PageParams:
    return PageParams(page=page, per_page=per_page, sort=sort)
