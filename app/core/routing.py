"""ApiRouter: дефолты для всех роутов API (envelope без None-полей)."""

from typing import Any

from fastapi import APIRouter


class ApiRouter(APIRouter):
    """APIRouter с настройками, едиными для всего API.

    ``response_model_exclude_none=True`` — поля с None (например ``meta``
    у непагинированных ответов) опускаются из JSON, как требует api.md.
    """

    def api_route(self, *args: Any, **kwargs: Any) -> Any:
        # Декораторы APIRouter всегда явно передают response_model_exclude_none,
        # поэтому перекрываем значение, а не используем setdefault.
        kwargs["response_model_exclude_none"] = True
        return super().api_route(*args, **kwargs)


__all__ = ["ApiRouter"]
