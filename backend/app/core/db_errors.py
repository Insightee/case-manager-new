from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError


def raise_db_write_http_error(exc: OperationalError) -> None:
    message = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
    lowered = message.lower()
    if "readonly" in lowered or "read-only" in lowered:
        raise HTTPException(
            status_code=503,
            detail=(
                "Database is read-only. Restart the API from the backend folder "
                "(cd backend && uvicorn app.main:app --reload --port 8000) and ensure "
                "backend/insightcase.db is writable."
            ),
        ) from exc
    if "locked" in lowered:
        raise HTTPException(
            status_code=503,
            detail="Database is busy. Wait a moment and try again.",
        ) from exc
    raise HTTPException(status_code=500, detail="Database error") from exc


def commit_or_http(db) -> None:
    try:
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise_db_write_http_error(exc)
