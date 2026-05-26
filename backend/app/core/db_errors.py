from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from app.core.config import settings

_readonly_pool_reset_done = False


def raise_db_write_http_error(exc: OperationalError) -> None:
    global _readonly_pool_reset_done
    message = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
    lowered = message.lower()
    if "readonly" in lowered or "read-only" in lowered:
        if settings.is_sqlite and not _readonly_pool_reset_done:
            from app.core.database import engine

            engine.dispose()
            _readonly_pool_reset_done = True
        raise HTTPException(
            status_code=503,
            detail=(
                "Database is read-only. Restart the API from the backend folder "
                "(cd backend && uvicorn app.main:app --reload --port 8000) and ensure "
                "backend/insightcase.db is writable. If this persists after restart, "
                "re-run: python3 -m app.seed.demo_seed"
            ),
        ) from exc
    if "locked" in lowered:
        raise HTTPException(
            status_code=503,
            detail="Database is busy. Wait a moment and try again.",
        ) from exc
    if "no such column" in lowered or "no such table" in lowered:
        hint = (
            "Database schema is out of date (missing table or column). "
            "Restart the API from backend/ so migrations run on startup. "
            "SQLite: python3 -m app.seed.demo_seed after restart. "
            "Postgres: alembic upgrade head from backend/."
        )
        if settings.is_development:
            hint += f" Technical detail: {message[:240]}"
        raise HTTPException(status_code=503, detail=hint) from exc
    if settings.is_development:
        raise HTTPException(status_code=500, detail=f"Database error: {message[:320]}") from exc
    raise HTTPException(status_code=500, detail="Database error") from exc


def commit_or_http(db) -> None:
    try:
        db.commit()
    except OperationalError as exc:
        db.rollback()
        raise_db_write_http_error(exc)
