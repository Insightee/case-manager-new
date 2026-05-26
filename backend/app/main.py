from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import ensure_sqlite_schema_patches
from app.core.db_errors import raise_db_write_http_error
from app.core.production_checks import validate_production_settings
from app.db.bootstrap import bootstrap_schema

app = FastAPI(title="InsightCase API", version="0.1.0")


@app.exception_handler(OperationalError)
async def operational_error_handler(_request: Request, exc: OperationalError):
    try:
        raise_db_write_http_error(exc)
    except HTTPException as http_exc:
        return JSONResponse(status_code=http_exc.status_code, content={"detail": http_exc.detail})


def _verify_sqlite_writable() -> None:
    """Fail fast when the SQLite file cannot accept writes (stale connections are fixed via WAL + restart)."""
    if not settings.is_sqlite:
        return
    from app.core.database import engine

    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS _api_write_probe (id INTEGER PRIMARY KEY)"))
            conn.execute(text("INSERT INTO _api_write_probe DEFAULT VALUES"))
    except OperationalError as exc:
        import logging

        logging.getLogger("insightcase").error(
            "SQLite write probe failed for %s: %s — restart uvicorn from backend/",
            settings.database_url,
            exc,
        )


@app.on_event("startup")
def _on_startup() -> None:
    validate_production_settings()
    bootstrap_schema()
    ensure_sqlite_schema_patches()
    _verify_sqlite_writable()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "service": "InsightCase API",
        "health": "/health",
        "api": "/api/v1",
        "docs": "/docs",
        "ui": "Start the React app: cd frontend && npm run dev — then open http://localhost:5173",
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    revision = None
    try:
        row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
        revision = row[0] if row else None
    except Exception:
        revision = None
    return {"status": "ok", "db_migration": revision}
