"""session_time_audit_events — append-only time edit trail.

Revision ID: x1y2z3a4b5c6
Revises: w1x2y3z4a5b6
Create Date: 2026-07-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_table

revision: str = "x1y2z3a4b5c6"
down_revision: Union[str, None] = "w1x2y3z4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("session_time_audit_events"):
        op.create_table(
            "session_time_audit_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("previous_start_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("previous_end_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("new_start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("new_end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("edit_reason", sa.String(length=512), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    create_index_if_missing("ix_session_time_audit_events_session_id", "session_time_audit_events", ["session_id"])


def downgrade() -> None:
    if has_table("session_time_audit_events"):
        op.drop_table("session_time_audit_events")
