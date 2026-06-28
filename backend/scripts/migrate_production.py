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
from app.db.alembic_version_cleanup import all_stored_revisions, compact_stale_version_rows, current_revision

import app.models  # noqa: F401

# Columns that must exist when Alembic reports head (catches false stamps on partial upgrades).
_REQUIRED_AT_HEAD: dict[str, tuple[str, ...]] = {
    "users": ("external_employee_id",),
    "children": ("external_client_id",),
    "cases": ("external_case_ref",),
    "daily_logs": (
        "session_notes",
        "goals_addressed",
        "follow_ups",
        "parent_feedback_public",
        "parent_notified_at",
        "resubmitted_at",
        "visibility_status",
        "late_addition",
        "created_at",
    ),
    "case_assignments": (
        "therapist_accepted_at",
        "parent_accepted_at",
        "assignment_offer_sent_at",
    ),
    "email_suppressions": ("email",),
    "email_logs": ("attempt_count", "entity_type"),
    "invite_tokens": ("email_delivery_status",),
}


def _missing_required_columns(insp) -> list[str]:
    missing: list[str] = []
    for table, cols in _REQUIRED_AT_HEAD.items():
        if not insp.has_table(table):
            missing.extend(f"{table}.{c}" for c in cols)
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        for col in cols:
            if col not in existing:
                missing.append(f"{table}.{col}")
    return missing


def _bootstrap_empty_database(cfg: Config, script: ScriptDirectory) -> None:
    """Greenfield Postgres: create_all via bootstrap revision, then stamp head(s).

    Must run before any incremental ``upgrade("heads")`` — incremental migrations
    recreate enums/tables that bootstrap already materialized from current models.
    """
    heads = script.get_heads()
    print("Empty database — running bootstrap revision 70ed65093b89...")
    command.upgrade(cfg, "70ed65093b89")
    head = _resolve_head(cfg, script)
    print(f"Stamping alembic ({head}) after model bootstrap...")
    command.stamp(cfg, head)


_DAILY_LOGS_REPAIR_DDL: tuple[tuple[str, str], ...] = (
    ("session_notes", "TEXT"),
    ("goals_addressed", "TEXT"),
    ("follow_ups", "TEXT"),
    ("parent_session_rating", "INTEGER"),
    ("parent_feedback", "TEXT"),
    ("parent_feedback_at", "TIMESTAMPTZ"),
    ("parent_feedback_public", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("parent_notified_at", "TIMESTAMPTZ"),
    ("review_note", "TEXT"),
    ("resubmitted_at", "TIMESTAMPTZ"),
    ("visibility_status", "VARCHAR(32) NOT NULL DEFAULT 'INTERNAL_ONLY'"),
    ("late_addition", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("late_reason", "TEXT"),
    ("created_at", "TIMESTAMPTZ NOT NULL DEFAULT now()"),
)


def _repair_daily_logs_columns() -> list[str]:
    """Postgres-only idempotent column adds when Alembic skipped due to 'heads' stamp."""
    if settings.is_sqlite:
        return []
    insp = inspect(engine)
    if not insp.has_table("daily_logs"):
        return []
    existing = {c["name"] for c in insp.get_columns("daily_logs")}
    added: list[str] = []
    with engine.begin() as conn:
        for col, ddl in _DAILY_LOGS_REPAIR_DDL:
            if col in existing:
                continue
            conn.execute(text(f"ALTER TABLE daily_logs ADD COLUMN IF NOT EXISTS {col} {ddl}"))
            added.append(col)
    if added:
        print(f"Repaired daily_logs columns: {added}")
    return added


def _reconcile_heads_literal(cfg: Config, script: ScriptDirectory) -> None:
    """Replace alembic_version='heads' so incremental migrations actually run.

    Greenfield bootstrap historically stamped the literal string ``heads``. Alembic
    treats that as already at head and skips ``upgrade()``, leaving schema drift.
    """
    versions = all_stored_revisions(engine)
    if "heads" not in versions:
        return
    restamp = "p0q1r2s3t4u5"
    if script.get_revision(restamp) is None:
        head = _resolve_head(cfg, script)
        rev = script.get_revision(head)
        down = rev.down_revision if rev else None
        restamp = down[0] if isinstance(down, (tuple, list)) else down
    if not restamp:
        raise RuntimeError("Cannot reconcile alembic_version='heads' without a parent revision")
    print(
        "Replacing invalid alembic_version 'heads' with revision "
        f"{restamp} so pending migrations can apply..."
    )
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alembic_version WHERE version_num = 'heads'"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
            {"rev": restamp},
        )


def _resolve_head(cfg: Config, script: ScriptDirectory) -> str:
    heads = script.get_heads()
    if len(heads) > 1:
        print(f"Multiple Alembic heads detected ({heads}); upgrading all branches...")
        command.upgrade(cfg, "heads")
        heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected a single Alembic head after upgrade; got: {heads}")
    return heads[0]


def _next_revisions(script: ScriptDirectory, current: str | None) -> list[str]:
    if current is None:
        return []
    rev = script.get_revision(current)
    if rev is None:
        return []
    nextrev = rev.nextrev
    if not nextrev:
        return []
    if isinstance(nextrev, (tuple, list)):
        return list(nextrev)
    return [nextrev]


def _upgrade_with_drift_tolerance(cfg: Config, script: ScriptDirectory, head: str) -> None:
    """Step migrations forward; stamp past revisions whose objects already exist."""
    max_steps = 500
    for _ in range(max_steps):
        current = current_revision(engine, script)
        if current == head:
            return
        before = current
        try:
            command.upgrade(cfg, "+1")
        except Exception as exc:
            err = str(exc).lower()
            if "duplicate" not in err and "already exists" not in err:
                raise
            after = current_revision(engine, script)
            if after != before:
                print(f"Partial migration applied ({before} -> {after}); continuing...")
                continue
            targets = _next_revisions(script, before)
            if len(targets) != 1:
                raise RuntimeError(
                    f"Cannot auto-stamp past drift at {before!r} "
                    f"(ambiguous next revisions {targets}): {exc}"
                ) from exc
            target = targets[0]
            print(
                f"Schema drift at {target} (objects already exist); "
                f"stamping {before or '(none)'} -> {target}..."
            )
            command.stamp(cfg, target)
            continue
    raise RuntimeError(f"Migration loop exceeded {max_steps} steps without reaching {head}")


def main() -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    script = ScriptDirectory.from_config(cfg)
    insp = inspect(engine)

    if not insp.has_table("users"):
        _bootstrap_empty_database(cfg, script)
        return

    head = _resolve_head(cfg, script)

    compact_stale_version_rows(engine, script)
    _reconcile_heads_literal(cfg, script)
    _repair_daily_logs_columns()
    current = current_revision(engine, script)
    missing = _missing_required_columns(insp)
    if current == head and not missing:
        print(f"Database already at head ({head}).")
        return

    if missing:
        print(f"Schema drift: missing {missing}; migrating to head ({head})...")

    print(f"Migrating {current or '(none)'} -> {head}...")
    _upgrade_with_drift_tolerance(cfg, script, head)

    missing_after = _missing_required_columns(inspect(engine))
    if missing_after:
        _repair_daily_logs_columns()
        missing_after = _missing_required_columns(inspect(engine))
    if missing_after:
        raise RuntimeError(
            f"Migration finished but required columns still missing: {missing_after}. "
            "Do not start the API until Alembic head is fully applied."
        )
    final = current_revision(engine, script)
    print(f"Migration complete (revision {final}).")


if __name__ == "__main__":
    if settings.is_sqlite:
        from app.core.database import ensure_sqlite_schema_patches
        from app.db.bootstrap import bootstrap_schema

        bootstrap_schema()
        ensure_sqlite_schema_patches()
        print("SQLite dev: applied bootstrap + schema patches (skipped Alembic; use Postgres + main() in prod).")
    else:
        main()
