"""Pydantic V2 schemas package."""

from app.schemas.common import (
    DataResponse,
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    PageMeta,
)

__all__ = ["DataResponse", "ErrorBody", "ErrorDetail", "ErrorResponse", "PageMeta"]
