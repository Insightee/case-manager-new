"""Migration adds daily_logs.visibility_status when missing (Postgres schema drift)."""
from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.core.database import Base


def test_visibility_status_backfill_sql():
    """Mirrors q1r2s3t4u5v6 migration: add column + indexes when missing."""
    import app.models  # noqa: F401

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    with eng.begin() as conn:
        for idx in (
            "ix_daily_logs_visibility_status",
            "ix_daily_logs_approval_visibility_submitted",
        ):
            conn.execute(text(f"DROP INDEX IF EXISTS {idx}"))
        conn.execute(text("ALTER TABLE daily_logs DROP COLUMN visibility_status"))
        conn.execute(
            text(
                "ALTER TABLE daily_logs ADD COLUMN visibility_status "
                "VARCHAR(32) NOT NULL DEFAULT 'INTERNAL_ONLY'"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_daily_logs_visibility_status "
                "ON daily_logs (visibility_status)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_daily_logs_approval_visibility_submitted "
                "ON daily_logs (approval_status, visibility_status, submitted_at)"
            )
        )

    cols = {c["name"] for c in inspect(eng).get_columns("daily_logs")}
    assert "visibility_status" in cols
    indexes = {idx["name"] for idx in inspect(eng).get_indexes("daily_logs")}
    assert "ix_daily_logs_visibility_status" in indexes
    assert "ix_daily_logs_approval_visibility_submitted" in indexes

    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO daily_logs (session_id, attendance_status, visibility_status, "
                "approval_status, late_addition, parent_feedback_public) "
                "VALUES (1, 'PRESENT', 'INTERNAL_ONLY', 'PENDING', 0, 0)"
            )
        )

    eng.dispose()
