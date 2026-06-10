"""Add edited_start_at/edited_end_at for therapist time corrections."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("sessions", "edited_start_at"):
        op.add_column(
            "sessions",
            sa.Column("edited_start_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column("sessions", "edited_end_at"):
        op.add_column(
            "sessions",
            sa.Column("edited_end_at", sa.DateTime(timezone=True), nullable=True),
        )

    # Backfill: rows edited under old overwrite behavior keep actual_* as effective;
    # copy to edited_* so UI can show correction consistently.
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.execute(
            sa.text(
                """
                UPDATE sessions
                SET edited_start_at = actual_start_at,
                    edited_end_at = actual_end_at
                WHERE actual_times_edited = true
                  AND actual_start_at IS NOT NULL
                  AND actual_end_at IS NOT NULL
                  AND edited_start_at IS NULL
                """
            )
        )


def downgrade() -> None:
    if _has_column("sessions", "edited_end_at"):
        op.drop_column("sessions", "edited_end_at")
    if _has_column("sessions", "edited_start_at"):
        op.drop_column("sessions", "edited_start_at")
