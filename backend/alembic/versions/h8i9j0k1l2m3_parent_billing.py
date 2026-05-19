"""parent billing statements

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parent_billing_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_user_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("month", sa.String(length=32), nullable=False),
        sa.Column("amount_inr", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("DUE", "PAID", name="parentbillingstatus"), nullable=False),
        sa.Column("detail", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parent_billing_statements_parent_user_id", "parent_billing_statements", ["parent_user_id"])
    op.create_index("ix_parent_billing_statements_case_id", "parent_billing_statements", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_parent_billing_statements_case_id", table_name="parent_billing_statements")
    op.drop_index("ix_parent_billing_statements_parent_user_id", table_name="parent_billing_statements")
    op.drop_table("parent_billing_statements")
