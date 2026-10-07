"""Append-only status history for end-of-day ops snapshots.

Revision ID: 31fb30395ec2
Revises: st4ff4tt3nd2
Create Date: 2026-10-07 04:16:33.570144

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "31fb30395ec2"
down_revision: Union[str, None] = "st4ff4tt3nd2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("ops_state_transitions"):
        return
    op.create_table(
        "ops_state_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=32), nullable=False),
        sa.Column("old_value", sa.String(length=64), nullable=True),
        sa.Column("new_value", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ops_state_transitions_lookup",
        "ops_state_transitions",
        ["entity_type", "entity_id", "occurred_at"],
    )


def downgrade() -> None:
    if not has_table("ops_state_transitions"):
        return
    op.drop_index("ix_ops_state_transitions_lookup", table_name="ops_state_transitions")
    op.drop_table("ops_state_transitions")
