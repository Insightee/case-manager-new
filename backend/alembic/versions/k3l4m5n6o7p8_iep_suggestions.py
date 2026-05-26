"""IEP plan suggestions for parent/therapist feedback

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-05-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k3l4m5n6o7p8"
down_revision: Union[str, None] = "j2k3l4m5n6o7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "iep_plan_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("iep_plan_id", sa.Integer(), sa.ForeignKey("iep_plans.id"), nullable=False, index=True),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("author_role", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("iep_plan_suggestions")
