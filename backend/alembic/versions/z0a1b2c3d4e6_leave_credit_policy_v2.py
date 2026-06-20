"""Leave credit policy v2: split days, multi-case, parent consultation flag."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "z0a1b2c3d4e6"
down_revision = "y8z9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("therapist_leaves", sa.Column("case_ids", sa.JSON(), nullable=True))
    op.add_column("therapist_leaves", sa.Column("paid_days", sa.Integer(), nullable=True))
    op.add_column("therapist_leaves", sa.Column("unpaid_days", sa.Integer(), nullable=True))
    op.add_column(
        "therapist_leaves",
        sa.Column("consulted_with_parents", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "therapist_leaves",
        sa.Column("includes_shadow_cases", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("therapist_leaves", "includes_shadow_cases")
    op.drop_column("therapist_leaves", "consulted_with_parents")
    op.drop_column("therapist_leaves", "unpaid_days")
    op.drop_column("therapist_leaves", "paid_days")
    op.drop_column("therapist_leaves", "case_ids")
