"""client status management — new enum values, status audit columns, and audit table

Revision ID: b5c6d7e8f9a0
Revises: 9585b848844d
Create Date: 2026-06-16 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

from migration_util import has_column, has_table

revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "9585b848844d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns to cases table
    with op.batch_alter_table("cases", schema=None) as batch_op:
        if not has_column("cases", "status_effective_date"):
            batch_op.add_column(sa.Column("status_effective_date", sa.Date(), nullable=True))
        if not has_column("cases", "status_reason"):
            batch_op.add_column(sa.Column("status_reason", sa.Text(), nullable=True))
        if not has_column("cases", "status_changed_by_user_id"):
            batch_op.add_column(sa.Column("status_changed_by_user_id", sa.Integer(), nullable=True))

    # 2. Create case_client_status_audit table
    if not has_table("case_client_status_audit"):
        op.create_table(
            "case_client_status_audit",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False, index=True),
            sa.Column("previous_status", sa.String(32), nullable=False),
            sa.Column("new_status", sa.String(32), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("internal_notes", sa.Text(), nullable=True),
            sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("case_client_status_audit")
    with op.batch_alter_table("cases", schema=None) as batch_op:
        batch_op.drop_column("status_changed_by_user_id")
        batch_op.drop_column("status_reason")
        batch_op.drop_column("status_effective_date")
