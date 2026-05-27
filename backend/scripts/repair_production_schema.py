#!/usr/bin/env python3
"""One-off repair when Alembic is behind but enums/tables partially exist.

Adds external ID columns if missing, ensures case_status_requests exists,
then stamps Alembic to head. Requires DATABASE_URL (use Railway DATABASE_PUBLIC_URL).

  cd backend
  export DATABASE_URL='postgresql+psycopg2://...'
  python3 scripts/repair_production_schema.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "alembic"))

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import engine

import app.models  # noqa: F401


def main() -> int:
    if settings.is_sqlite:
        print("Use Postgres DATABASE_URL (Railway DATABASE_PUBLIC_URL).", file=sys.stderr)
        return 1

    insp = inspect(engine)
    with engine.begin() as conn:
        if insp.has_table("users"):
            cols = {c["name"] for c in insp.get_columns("users")}
            if "external_employee_id" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN external_employee_id VARCHAR(64)"))
                print("Added users.external_employee_id")
        if insp.has_table("children"):
            cols = {c["name"] for c in insp.get_columns("children")}
            if "external_client_id" not in cols:
                conn.execute(text("ALTER TABLE children ADD COLUMN external_client_id VARCHAR(64)"))
                print("Added children.external_client_id")
        if insp.has_table("cases"):
            cols = {c["name"] for c in insp.get_columns("cases")}
            if "external_case_ref" not in cols:
                conn.execute(text("ALTER TABLE cases ADD COLUMN external_case_ref VARCHAR(128)"))
                print("Added cases.external_case_ref")

        conn.execute(
            text(
                """
                DO $$ BEGIN
                    CREATE TYPE casestatusrequeststatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        if not insp.has_table("case_status_requests"):
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS case_status_requests (
                        id SERIAL PRIMARY KEY,
                        case_id INTEGER NOT NULL REFERENCES cases(id),
                        requested_by_user_id INTEGER NOT NULL REFERENCES users(id),
                        from_status VARCHAR(32) NOT NULL,
                        to_status VARCHAR(32) NOT NULL,
                        reason TEXT NOT NULL,
                        status casestatusrequeststatus NOT NULL DEFAULT 'PENDING',
                        reviewed_by_user_id INTEGER REFERENCES users(id),
                        review_note TEXT,
                        created_at TIMESTAMPTZ DEFAULT now(),
                        reviewed_at TIMESTAMPTZ
                    )
                    """
                )
            )
            print("Ensured case_status_requests table")

    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    head = ScriptDirectory.from_config(cfg).get_current_head()
    print(f"Running alembic upgrade head ({head})...")
    try:
        command.upgrade(cfg, head)
    except Exception as exc:
        err = str(exc).lower()
        if "duplicate" not in err and "already exists" not in err:
            raise
        print(f"Upgrade note (continuing): {exc}")

    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
        print(f"alembic_version={row[0] if row else None}")
    print("Repair complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
