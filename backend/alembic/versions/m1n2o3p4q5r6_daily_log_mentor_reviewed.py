"""Add mentor review fields on daily_logs.

Revision ID: m1n2o3p4q5r6
Revises: b95440cc4d91
Create Date: 2026-08-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "m1n2o3p4q5r6"
down_revision: Union[str, Sequence[str], None] = "b95440cc4d91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("daily_logs") as batch_op:
        batch_op.add_column(sa.Column("mentor_reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("mentor_reviewed_by_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_daily_logs_mentor_reviewed_by_user_id",
            "users",
            ["mentor_reviewed_by_user_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("daily_logs") as batch_op:
        batch_op.drop_constraint("fk_daily_logs_mentor_reviewed_by_user_id", type_="foreignkey")
        batch_op.drop_column("mentor_reviewed_by_user_id")
        batch_op.drop_column("mentor_reviewed_at")
