"""Apply schema on Railway Postgres.

The initial Alembic revision bootstraps via SQLAlchemy ``create_all`` (current models).
Incremental revisions are idempotent where possible; on greenfield DBs we stamp ``head``
after bootstrap to avoid duplicate-column failures.
"""
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "alembic"))

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import engine

import app.models  # noqa: F401


def _current_revision() -> str | None:
    insp = inspect(engine)
    if not insp.has_table("alembic_version"):
        return None
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
    return row[0] if row else None


def _resolve_head(cfg: Config, script: ScriptDirectory) -> str:
    heads = script.get_heads()
    if len(heads) > 1:
        print(f"Multiple Alembic heads detected ({heads}); upgrading all branches...")
        command.upgrade(cfg, "heads")
        heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected a single Alembic head after upgrade; got: {heads}")
    return heads[0]


def main() -> None:
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    head = _resolve_head(cfg, script)
    insp = inspect(engine)

    if not insp.has_table("users"):
        print("Empty database — running bootstrap revision 70ed65093b89...")
        command.upgrade(cfg, "70ed65093b89")
        print(f"Stamping alembic head ({head}) after model bootstrap...")
        command.stamp(cfg, head)
        return

    current = _current_revision()
    if current == head:
        print(f"Database already at head ({head}).")
        return

    print(f"Migrating {current or '(none)'} -> {head}...")
    try:
        command.upgrade(cfg, head)
    except Exception as exc:
        # Only stamp when the DB already matches head (greenfield bootstrap path).
        # Do not stamp on partial failures — that leaves code ahead of schema.
        err = str(exc).lower()
        if "duplicate" in err or "already exists" in err:
            print(f"Upgrade hit existing object ({exc!r}); retrying upgrade to head...")
            command.upgrade(cfg, head)
            return
        raise


if __name__ == "__main__":
    if settings.is_sqlite:
        from app.core.database import ensure_sqlite_schema_patches
        from app.db.bootstrap import bootstrap_schema

        bootstrap_schema()
        ensure_sqlite_schema_patches()
        print("SQLite dev: applied bootstrap + schema patches (skipped Alembic; use Postgres + main() in prod).")
    else:
        main()
