"""Shared pagination helpers for list endpoints."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def normalize_pagination(page: int = 1, page_size: int = 25, max_page_size: int = 100) -> tuple[int, int]:
    page = max(1, page)
    page_size = max(1, min(page_size, max_page_size))
    return page, page_size


def paginate_query(
    db: Session,
    stmt: Select[Any],
    *,
    page: int = 1,
    page_size: int = 25,
    max_page_size: int = 100,
) -> tuple[list[Any], int]:
    page, page_size = normalize_pagination(page, page_size, max_page_size)
    subq = stmt.order_by(None).subquery()
    total = db.scalar(select(func.count()).select_from(subq)) or 0
    offset = (page - 1) * page_size
    rows = list(db.scalars(stmt.offset(offset).limit(page_size)).all())
    return rows, int(total)


def paginated_response(items: list[T], total: int, page: int, page_size: int) -> dict[str, Any]:
    pages = max(1, (total + page_size - 1) // page_size) if page_size else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }
