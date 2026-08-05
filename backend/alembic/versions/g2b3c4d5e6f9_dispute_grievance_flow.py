"""Dispute grievance flow — billing dispute tickets + correction resolution.

Revision ID: g2b3c4d5e6f9
Revises: f2a3b4c5d6e8
Create Date: 2026-08-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "g2b3c4d5e6f9"
down_revision: Union[str, None] = "f2a3b4c5d6e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("billing_disputes") and not has_column("billing_disputes", "support_ticket_id"):
        op.add_column(
            "billing_disputes",
            sa.Column("support_ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id"), nullable=True),
        )
        op.create_index("ix_billing_disputes_support_ticket_id", "billing_disputes", ["support_ticket_id"])

    if has_table("support_tickets"):
        if not has_column("support_tickets", "billing_dispute_id"):
            op.add_column(
                "support_tickets",
                sa.Column("billing_dispute_id", sa.Integer(), sa.ForeignKey("billing_disputes.id"), nullable=True),
            )
        if not has_column("support_tickets", "client_invoice_id"):
            op.add_column(
                "support_tickets",
                sa.Column("client_invoice_id", sa.Integer(), sa.ForeignKey("client_invoices.id"), nullable=True),
            )

    if has_table("finance_correction_proposals") and not has_column(
        "finance_correction_proposals", "billing_dispute_id"
    ):
        op.add_column(
            "finance_correction_proposals",
            sa.Column("billing_dispute_id", sa.Integer(), sa.ForeignKey("billing_disputes.id"), nullable=True),
        )


def downgrade() -> None:
    if has_table("finance_correction_proposals") and has_column("finance_correction_proposals", "billing_dispute_id"):
        op.drop_column("finance_correction_proposals", "billing_dispute_id")
    if has_table("support_tickets"):
        if has_column("support_tickets", "client_invoice_id"):
            op.drop_column("support_tickets", "client_invoice_id")
        if has_column("support_tickets", "billing_dispute_id"):
            op.drop_column("support_tickets", "billing_dispute_id")
    if has_table("billing_disputes") and has_column("billing_disputes", "support_ticket_id"):
        op.drop_index("ix_billing_disputes_support_ticket_id", table_name="billing_disputes")
        op.drop_column("billing_disputes", "support_ticket_id")
