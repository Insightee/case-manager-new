"""add monthly therapist payout flags

Revision ID: pf4g5h6i7j8
Revises: tk3c4d5e6f7
Create Date: 2026-08-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "pf4g5h6i7j8"
down_revision: Union[str, None] = "tk3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "therapist_payout_flags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("billing_month", sa.String(length=7), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("outgoing_assignment_id", sa.Integer(), nullable=False),
        sa.Column("flagged_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_invoice_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["cleared_invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(
            ["flagged_by_user_id"], ["users.id"]
        ),
        sa.ForeignKeyConstraint(
            ["outgoing_assignment_id"], ["case_assignments.id"]
        ),
        sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_therapist_payout_flags_active_month",
        "therapist_payout_flags",
        ["therapist_user_id", "billing_month", "is_active"],
    )
    op.create_index(
        "ix_therapist_payout_flags_billing_month",
        "therapist_payout_flags",
        ["billing_month"],
    )
    op.create_index(
        "ix_therapist_payout_flags_case_id",
        "therapist_payout_flags",
        ["case_id"],
    )
    op.create_index(
        "ix_therapist_payout_flags_therapist_user_id",
        "therapist_payout_flags",
        ["therapist_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_therapist_payout_flags_therapist_user_id",
        table_name="therapist_payout_flags",
    )
    op.drop_index(
        "ix_therapist_payout_flags_case_id",
        table_name="therapist_payout_flags",
    )
    op.drop_index(
        "ix_therapist_payout_flags_billing_month",
        table_name="therapist_payout_flags",
    )
    op.drop_index(
        "ix_therapist_payout_flags_active_month",
        table_name="therapist_payout_flags",
    )
    op.drop_table("therapist_payout_flags")
