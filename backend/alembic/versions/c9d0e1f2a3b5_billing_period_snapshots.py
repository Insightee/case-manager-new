"""Billing period snapshots + client invoice billing_snapshot.

Revision ID: c9d0e1f2a3b5
Revises: b8c9d0e1f2a4
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "c9d0e1f2a3b5"
down_revision: Union[str, None] = "b8c9d0e1f2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("billing_month_closes"):
        op.create_table(
            "billing_month_closes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("billing_month", sa.String(length=32), nullable=False),
            sa.Column(
                "status",
                sa.Enum("CLOSED", name="billingmonthclosestatus"),
                nullable=False,
                server_default="CLOSED",
            ),
            sa.Column("payout_preview_rows", sa.JSON(), nullable=False),
            sa.Column("closed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("closed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.UniqueConstraint("billing_month", name="uq_billing_month_closes_month"),
        )
        op.create_index("ix_billing_month_closes_billing_month", "billing_month_closes", ["billing_month"])

    if not has_table("case_billing_period_snapshots"):
        op.create_table(
            "case_billing_period_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("billing_month", sa.String(length=32), nullable=False),
            sa.Column("billing_snapshot", sa.JSON(), nullable=True),
            sa.Column("client_invoice_id", sa.Integer(), sa.ForeignKey("client_invoices.id"), nullable=True),
            sa.Column("ledger_subtotal_inr", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("ledger_tax_inr", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("ledger_total_inr", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("margin_inr", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("therapist_payout_total_inr", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("session_count", sa.Integer(), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("closed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.UniqueConstraint(
                "case_id",
                "billing_month",
                name="uq_case_billing_period_snapshots_case_month",
            ),
        )
        op.create_index(
            "ix_case_billing_period_snapshots_case_id",
            "case_billing_period_snapshots",
            ["case_id"],
        )
        op.create_index(
            "ix_case_billing_period_snapshots_billing_month",
            "case_billing_period_snapshots",
            ["billing_month"],
        )

    if has_table("client_invoices") and not has_column("client_invoices", "billing_snapshot"):
        with op.batch_alter_table("client_invoices", schema=None) as batch_op:
            batch_op.add_column(sa.Column("billing_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    if has_table("client_invoices") and has_column("client_invoices", "billing_snapshot"):
        with op.batch_alter_table("client_invoices", schema=None) as batch_op:
            batch_op.drop_column("billing_snapshot")

    if has_table("case_billing_period_snapshots"):
        op.drop_table("case_billing_period_snapshots")

    if has_table("billing_month_closes"):
        op.drop_table("billing_month_closes")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS billingmonthclosestatus"))
