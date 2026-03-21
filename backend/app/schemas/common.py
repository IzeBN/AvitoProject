"""
Общие схемы ответов API: пагинация, ошибки, успех.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field
import math

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Ответ с пагинацией для списковых эндпоинтов."""

    items: list[T]
    total: int = Field(description="Общее количество записей")
    page: int = Field(ge=1, description="Текущая страница")
    page_size: int = Field(ge=1, le=200, description="Размер страницы")
    pages: int = Field(description="Общее количество страниц")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        pages = max(1, math.ceil(total / page_size)) if page_size > 0 else 1
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class ErrorDetail(BaseModel):
    """Детали ошибки."""

    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    """Стандартный ответ об ошибке."""

    detail: str
    errors: list[ErrorDetail] | None = None
    request_id: str | None = None


class SuccessResponse(BaseModel):
    """Стандартный ответ об успехе операции."""

    message: str
    request_id: str | None = None
