"""Ensure database schema exists before serving traffic."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import Base, engine
import app.models  # noqa: F401


def bootstrap_schema() -> None:
    """SQLite dev: create any missing tables from models; Postgres uses Alembic."""
    if not settings.is_sqlite:
        return
    # Safe on existing DBs — only creates tables that are not present yet.
    Base.metadata.create_all(bind=engine)

    insp = inspect(engine)
    with engine.connect() as conn:
        if not insp.has_table("alembic_version"):
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS alembic_version "
                    "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                )
            )
            conn.commit()
