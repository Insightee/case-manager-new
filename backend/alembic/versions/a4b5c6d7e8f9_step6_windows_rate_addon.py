"""Step 6: assignment windows, rate periods, add-on kind — staging first.

Revision ID: a4b5c6d7e8f9
Revises: z3a4b5c6d7e8
Create Date: 2026-08-02

- sessions.add_on_kind / parent_session_id (legacy is_additional_visit mapped, no ledger rewrite)
- case_client_rate_periods for mid-month client rate changes
- billing_calc_exceptions for Step 6 exception codes
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from migration_util import has_column, has_table

revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "z3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        if not has_column("sessions", "add_on_kind"):
            batch_op.add_column(sa.Column("add_on_kind", sa.String(length=32), nullable=True))
        if not has_column("sessions", "parent_session_id"):
            batch_op.add_column(sa.Column("parent_session_id", sa.Integer(), nullable=True))

    # Metadata-only legacy map: do NOT touch billing_ledger (financial history stays intact).
    conn = op.get_bind()
    if has_column("sessions", "add_on_kind") and has_column("sessions", "is_additional_visit"):
        conn.execute(
            text(
                "UPDATE sessions SET add_on_kind = 'EXTRA_DAY' "
                "WHERE is_additional_visit IS TRUE AND (add_on_kind IS NULL OR add_on_kind = '')"
            )
        )

    if not has_table("case_client_rate_periods"):
        op.create_table(
            "case_client_rate_periods",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("rate_inr", sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column("label", sa.String(length=32), nullable=False, server_default="normal"),
            sa.Column("effective_date_choice", sa.String(length=32), nullable=True),
            sa.Column("resolved_effective_date", sa.Date(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("notes", sa.Text(), nullable=True),
        )
        op.create_index("ix_case_client_rate_periods_case_id", "case_client_rate_periods", ["case_id"])

    if not has_table("billing_calc_exceptions"):
        op.create_table(
            "billing_calc_exceptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("ledger_month", sa.String(length=32), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("message", sa.String(length=512), nullable=False),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_billing_calc_exceptions_case_id", "billing_calc_exceptions", ["case_id"])
        op.create_index(
            "ix_billing_calc_exceptions_ledger_month", "billing_calc_exceptions", ["ledger_month"]
        )


def downgrade() -> None:
    if has_table("billing_calc_exceptions"):
        op.drop_table("billing_calc_exceptions")
    if has_table("case_client_rate_periods"):
        op.drop_table("case_client_rate_periods")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        if has_column("sessions", "parent_session_id"):
            batch_op.drop_column("parent_session_id")
        if has_column("sessions", "add_on_kind"):
            batch_op.drop_column("add_on_kind")
