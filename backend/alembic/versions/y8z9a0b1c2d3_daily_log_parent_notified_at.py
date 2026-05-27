"""Add parent_notified_at to daily_logs for onboarding audit trail."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "y8z9a0b1c2d3"
down_revision = "x7y8z9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_logs",
        sa.Column("parent_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_daily_logs_parent_notified_at", "daily_logs", ["parent_notified_at"])


def downgrade() -> None:
    op.drop_index("ix_daily_logs_parent_notified_at", table_name="daily_logs")
    op.drop_column("daily_logs", "parent_notified_at")
