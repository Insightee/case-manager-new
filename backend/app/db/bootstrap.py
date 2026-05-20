"""Ensure database schema exists before serving traffic."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.database import Base, engine
import app.models  # noqa: F401


def bootstrap_schema() -> None:
    """Create tables on empty DB; run Alembic separately for incremental upgrades."""
    insp = inspect(engine)
    if not insp.has_table("users"):
        Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        if not insp.has_table("alembic_version"):
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS alembic_version "
                    "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                )
            )
            conn.commit()
