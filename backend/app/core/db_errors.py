from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from app.core.config import settings

_log = logging.getLogger("insightcase")
_readonly_pool_reset_done = False


def _log_db_error(exc: Exception) -> str:
    message = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
    _log.error("Database write failed: %s", message, exc_info=exc)
    return message


def _detail_with_optional_technical(hint: str, message: str) -> str:
    if settings.expose_db_error_detail:
        return f"{hint} Technical detail: {message[:320]}"
    return hint


def raise_db_write_http_error(exc: OperationalError) -> None:
    global _readonly_pool_reset_done
    message = _log_db_error(exc)
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
    if "timeout expired" in lowered or "could not connect" in lowered or "connection refused" in lowered:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cannot reach the database. For local dev without Docker, start the API from backend/ "
                "without DATABASE_URL (uses SQLite), or run: docker compose up -d postgres redis"
            ),
        ) from exc
    if "no such column" in lowered or "no such table" in lowered:
        hint = (
            "Database schema is out of date (missing table or column). "
            "Restart the API from backend/ so migrations run on startup. "
            "SQLite: python3 -m app.seed.demo_seed after restart. "
            "Postgres: alembic upgrade head from backend/."
        )
        raise HTTPException(status_code=503, detail=_detail_with_optional_technical(hint, message)) from exc
    if "does not exist" in lowered and ("column" in lowered or "relation" in lowered):
        hint = (
            "Database schema is out of date (missing table or column). "
            "Redeploy the API so migrations run, or run python scripts/migrate_production.py."
        )
        raise HTTPException(status_code=503, detail=_detail_with_optional_technical(hint, message)) from exc
    if settings.expose_db_error_detail:
        raise HTTPException(status_code=500, detail=f"Database error: {message[:320]}") from exc
    raise HTTPException(status_code=500, detail="Database error") from exc


def raise_db_integrity_http_error(exc: IntegrityError) -> None:
    message = _log_db_error(exc)
    lowered = message.lower()
    if "foreign key" in lowered or "violates foreign key constraint" in lowered:
        raise HTTPException(
            status_code=400,
            detail="One of the selected staff members is no longer valid. Refresh the page and try again.",
        ) from exc
    raise HTTPException(status_code=400, detail="Could not save — a database constraint was violated.") from exc


def raise_db_api_http_error(exc: DBAPIError) -> None:
    message = _log_db_error(exc)
    lowered = message.lower()
    if "invalid input value for enum" in lowered and "casestatus" in lowered:
        raise HTTPException(
            status_code=503,
            detail=(
                "Database schema is out of date (case status enum). "
                "Run alembic upgrade head on the API service, then try again."
            ),
        ) from exc
    if "invalid input value for enum" in lowered and "meetingtype" in lowered:
        raise HTTPException(
            status_code=503,
            detail=(
                "Database schema is out of date (meeting type enum). "
                "Run alembic upgrade head on the API service, then try again."
            ),
        ) from exc
    if "invalid input value for enum" in lowered and "meetingstatus" in lowered:
        raise HTTPException(
            status_code=503,
            detail=(
                "Database schema is out of date (meeting status enum). "
                "Run alembic upgrade head on the API service, then try again."
            ),
        ) from exc
    if "invalid input value for enum" in lowered and "logapprovalstatus" in lowered:
        raise HTTPException(
            status_code=503,
            detail=_detail_with_optional_technical(
                "Database schema is out of date (session log approval status). "
                "Redeploy the API so migrations run, then try again.",
                message,
            ),
        ) from exc
    if isinstance(exc, OperationalError):
        raise_db_write_http_error(exc)
    if settings.expose_db_error_detail:
        raise HTTPException(status_code=500, detail=f"Database error: {message[:320]}") from exc
    raise HTTPException(status_code=500, detail="Database error") from exc


def commit_or_http(db) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise_db_integrity_http_error(exc)
    except OperationalError as exc:
        db.rollback()
        raise_db_write_http_error(exc)
    except DBAPIError as exc:
        db.rollback()
        raise_db_api_http_error(exc)
