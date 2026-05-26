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


def _log_schema_health() -> None:
    """Warn in logs when ledger-billing columns are missing (common after pull without API restart)."""
    import logging

    from sqlalchemy import inspect

    from app.core.database import engine

    log = logging.getLogger("insightcase")
    try:
        insp = inspect(engine)
        if insp.has_table("cases"):
            cols = {c["name"] for c in insp.get_columns("cases")}
            if "product_billing_rule_id" not in cols:
                log.error(
                    "Schema drift: cases.product_billing_rule_id missing. "
                    "Restart uvicorn from backend/ or run alembic upgrade head."
                )
    except Exception as exc:
        log.warning("Schema health check skipped: %s", exc)


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


def _maybe_seed_demo_on_empty_db() -> None:
    """First-run local dev: create demo users when the database has no accounts."""
    if settings.app_env not in ("development", "dev", "local"):
        return
    import logging

    from sqlalchemy import func, select

    from app.core.database import SessionLocal
    from app.models.user import User

    log = logging.getLogger("insightcase")
    db = SessionLocal()
    try:
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
    finally:
        db.close()
    if user_count > 0 and not settings.seed_demo_data:
        return
    if user_count > 0 and settings.seed_demo_data:
        log.info("SEED_DEMO_DATA=true — refreshing demo seed")
    elif user_count == 0:
        log.warning("No users in database — running demo seed (superadmin@demo.com / demo123)")
    else:
        return
    from app.seed.demo_seed import run

    run()
    log.info("Demo seed completed")


@app.on_event("startup")
def _on_startup() -> None:
    validate_production_settings()
    bootstrap_schema()
    ensure_sqlite_schema_patches()
    _maybe_seed_demo_on_empty_db()
    _verify_sqlite_writable()
    _log_schema_health()

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
