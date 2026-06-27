"""Idempotent repair for daily_logs columns missed when alembic_version was stamped 'heads'.

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
Create Date: 2026-06-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_column, has_table

revision: str = "r2s3t4u5v6w7"
down_revision: Union[str, None] = "q1r2s3t4u5v6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DAILY_LOG_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    ("session_notes", sa.Column("session_notes", sa.Text(), nullable=True)),
    ("goals_addressed", sa.Column("goals_addressed", sa.Text(), nullable=True)),
    ("follow_ups", sa.Column("follow_ups", sa.Text(), nullable=True)),
    ("parent_session_rating", sa.Column("parent_session_rating", sa.Integer(), nullable=True)),
    ("parent_feedback", sa.Column("parent_feedback", sa.Text(), nullable=True)),
    ("parent_feedback_at", sa.Column("parent_feedback_at", sa.DateTime(timezone=True), nullable=True)),
    (
        "parent_feedback_public",
        sa.Column(
            "parent_feedback_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    ),
    ("parent_notified_at", sa.Column("parent_notified_at", sa.DateTime(timezone=True), nullable=True)),
    ("review_note", sa.Column("review_note", sa.Text(), nullable=True)),
    ("resubmitted_at", sa.Column("resubmitted_at", sa.DateTime(timezone=True), nullable=True)),
    (
        "visibility_status",
        sa.Column(
            "visibility_status",
            sa.String(length=32),
            nullable=False,
            server_default="INTERNAL_ONLY",
        ),
    ),
    (
        "late_addition",
        sa.Column(
            "late_addition",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    ),
    ("late_reason", sa.Column("late_reason", sa.Text(), nullable=True)),
    (
        "created_at",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ),
)


def upgrade() -> None:
    if not has_table("daily_logs"):
        return
    for name, column in _DAILY_LOG_COLUMNS:
        if not has_column("daily_logs", name):
            op.add_column("daily_logs", column)
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
    if has_column("daily_logs", "parent_notified_at"):
        create_index_if_missing(
            "ix_daily_logs_parent_notified_at",
            "daily_logs",
            ["parent_notified_at"],
        )
    if has_column("daily_logs", "resubmitted_at"):
        create_index_if_missing(
            "ix_daily_logs_resubmitted_at",
            "daily_logs",
            ["resubmitted_at"],
        )


def downgrade() -> None:
    pass
