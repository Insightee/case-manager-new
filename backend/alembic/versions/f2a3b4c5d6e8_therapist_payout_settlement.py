"""Therapist payout settlement — batches, transfers, TDS override, invoice snapshots.

Revision ID: f2a3b4c5d6e8
Revises: e1f2a3b4c5d7
Create Date: 2026-08-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "f2a3b4c5d6e8"
down_revision: Union[str, None] = "e1f2a3b4c5d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_enum_value(enum_name: str, value: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def upgrade() -> None:
    if not has_table("therapist_payout_batches"):
        op.create_table(
            "therapist_payout_batches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("billing_month", sa.String(16), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
            sa.Column("provider", sa.String(32), nullable=False, server_default="MOCK"),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("provider_batch_ref", sa.String(128), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_therapist_payout_batches_billing_month", "therapist_payout_batches", ["billing_month"])
        op.create_unique_constraint(
            "uq_therapist_payout_batches_idempotency",
            "therapist_payout_batches",
            ["idempotency_key"],
        )

    if not has_table("therapist_payout_transfers"):
        op.create_table(
            "therapist_payout_transfers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("therapist_payout_batches.id"), nullable=False),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
            sa.Column("gross_inr", sa.Numeric(12, 2), nullable=False),
            sa.Column("tds_rate_percent", sa.Numeric(6, 2), nullable=False),
            sa.Column("tds_inr", sa.Numeric(12, 2), nullable=False),
            sa.Column("deductions_inr", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("net_inr", sa.Numeric(12, 2), nullable=False),
            sa.Column("provider_ref", sa.String(128), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_therapist_payout_transfers_batch_id", "therapist_payout_transfers", ["batch_id"])
        op.create_index("ix_therapist_payout_transfers_invoice_id", "therapist_payout_transfers", ["invoice_id"])
        bind = op.get_bind()
        if bind.dialect.name == "postgresql":
            op.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_therapist_payout_transfers_active_invoice
                ON therapist_payout_transfers (invoice_id)
                WHERE status IN ('PENDING', 'PROCESSING', 'PAID')
                """
            )

    _pg_enum_value("invoicestatus", "EXPORTING")

    if has_table("therapist_profiles") and not has_column("therapist_profiles", "tds_rate_percent"):
        op.add_column("therapist_profiles", sa.Column("tds_rate_percent", sa.Numeric(6, 2), nullable=True))

    if has_table("invoices"):
        if not has_column("invoices", "tds_inr"):
            op.add_column("invoices", sa.Column("tds_inr", sa.Numeric(12, 2), nullable=True))
        if not has_column("invoices", "net_payable_inr"):
            op.add_column("invoices", sa.Column("net_payable_inr", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    if has_table("invoices"):
        if has_column("invoices", "net_payable_inr"):
            op.drop_column("invoices", "net_payable_inr")
        if has_column("invoices", "tds_inr"):
            op.drop_column("invoices", "tds_inr")
    if has_table("therapist_profiles") and has_column("therapist_profiles", "tds_rate_percent"):
        op.drop_column("therapist_profiles", "tds_rate_percent")
    if has_table("therapist_payout_transfers"):
        bind = op.get_bind()
        if bind.dialect.name == "postgresql":
            op.execute("DROP INDEX IF EXISTS uq_therapist_payout_transfers_active_invoice")
        op.drop_table("therapist_payout_transfers")
    if has_table("therapist_payout_batches"):
        op.drop_table("therapist_payout_batches")
