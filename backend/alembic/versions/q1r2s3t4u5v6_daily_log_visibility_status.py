"""Add daily_logs.visibility_status for parent portal gating (schema drift fix).

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
Create Date: 2026-06-27

Older Postgres DBs bootstrapped before visibility_status existed on DailyLog fail
INSERT on POST /api/v1/daily-logs with a generic 500 Database error.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_column, has_index, has_table

revision: str = "q1r2s3t4u5v6"
down_revision: Union[str, None] = "p0q1r2s3t4u5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("daily_logs"):
        return
    if not has_column("daily_logs", "visibility_status"):
        op.add_column(
            "daily_logs",
            sa.Column(
                "visibility_status",
                sa.String(length=32),
                nullable=False,
                server_default="INTERNAL_ONLY",
            ),
        )
    if has_column("daily_logs", "visibility_status"):
        create_index_if_missing(
            "ix_daily_logs_visibility_status",
            "daily_logs",
            ["visibility_status"],
        )
        create_index_if_missing(
            "ix_daily_logs_approval_visibility_submitted",
            "daily_logs",
            ["approval_status", "visibility_status", "submitted_at"],
        )


def downgrade() -> None:
    if not has_table("daily_logs"):
        return
    if has_index("daily_logs", "ix_daily_logs_approval_visibility_submitted"):
        op.drop_index("ix_daily_logs_approval_visibility_submitted", table_name="daily_logs")
    if has_index("daily_logs", "ix_daily_logs_visibility_status"):
        op.drop_index("ix_daily_logs_visibility_status", table_name="daily_logs")
    if has_column("daily_logs", "visibility_status"):
        op.drop_column("daily_logs", "visibility_status")
