"""Case billing / remuneration rate change history with effective dates.

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "u5v6w7x8y9z0"
down_revision: Union[str, None] = "t4u5v6w7x8y9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("case_billing_rate_changes"):
        return
    op.create_table(
        "case_billing_rate_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("previous_client_amount_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_client_amount_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("previous_therapist_amount_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_therapist_amount_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("client_effective_from", sa.Date(), nullable=True),
        sa.Column("therapist_effective_from", sa.Date(), nullable=True),
        sa.Column("previous_snapshot", sa.JSON(), nullable=True),
        sa.Column("new_snapshot", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_billing_rate_changes_case_id", "case_billing_rate_changes", ["case_id"])
    op.create_index(
        "ix_case_billing_rate_changes_client_effective_from",
        "case_billing_rate_changes",
        ["client_effective_from"],
    )
    op.create_index(
        "ix_case_billing_rate_changes_therapist_effective_from",
        "case_billing_rate_changes",
        ["therapist_effective_from"],
    )
    op.create_index(
        "ix_case_billing_rate_changes_changed_by_user_id",
        "case_billing_rate_changes",
        ["changed_by_user_id"],
    )


def downgrade() -> None:
    if has_table("case_billing_rate_changes"):
        op.drop_table("case_billing_rate_changes")
