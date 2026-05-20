from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedList(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = Field(default=25, le=100)
    pages: int = 1
