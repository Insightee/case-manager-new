"""Finance writable Loop 2 — correction proposals, payout deductions, structured notes.

Revision ID: e1f2a3b4c5d7
Revises: d0e1f2a3b4c6
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "e1f2a3b4c5d7"
down_revision: Union[str, None] = "d0e1f2a3b4c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("finance_correction_proposals"):
        op.create_table(
            "finance_correction_proposals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("billing_month", sa.String(16), nullable=False),
            sa.Column("client_invoice_id", sa.Integer(), sa.ForeignKey("client_invoices.id"), nullable=True),
            sa.Column("therapist_invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=True),
            sa.Column(
                "proposal_type",
                sa.Enum(
                    "CORRECT_RESHARE",
                    "LINKED_AMOUNT_EDIT",
                    "PAYOUT_ONLY_EDIT",
                    name="financecorrectionproposaltype",
                ),
                nullable=False,
            ),
            sa.Column(
                "wrong_side",
                sa.Enum("INVOICE_WRONG", "RECORD_WRONG", name="financewrongside"),
                nullable=True,
            ),
            sa.Column(
                "status",
                sa.Enum("PENDING", "APPROVED", "REJECTED", "NEEDS_REVIEW", name="financeproposalstatus"),
                nullable=False,
                server_default="PENDING",
            ),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("old_client_amount_inr", sa.Numeric(12, 2), nullable=True),
            sa.Column("new_client_amount_inr", sa.Numeric(12, 2), nullable=True),
            sa.Column("old_payout_amount_inr", sa.Numeric(12, 2), nullable=True),
            sa.Column("new_payout_amount_inr", sa.Numeric(12, 2), nullable=True),
            sa.Column("case_share_ratio", sa.Numeric(16, 8), nullable=True),
            sa.Column("record_correction_payload", sa.JSON(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_finance_correction_proposals_case_month",
            "finance_correction_proposals",
            ["case_id", "billing_month"],
        )

    if not has_table("finance_payout_deductions"):
        op.create_table(
            "finance_payout_deductions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("billing_month", sa.String(16), nullable=False),
            sa.Column("therapist_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("therapist_invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=True),
            sa.Column("amount_inr", sa.Numeric(12, 2), nullable=False),
            sa.Column(
                "direction",
                sa.Enum("ADD", "DEDUCT", name="financepayoutdeductiondirection"),
                nullable=False,
            ),
            sa.Column(
                "note_type",
                sa.Enum(
                    "TRANSITION",
                    "RETAINER",
                    "DEDUCTION",
                    "NOTICE_PERIOD",
                    "OTHER",
                    name="casefinancenotetype",
                ),
                nullable=False,
            ),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column(
                "status",
                sa.Enum("ACTIVE", "REVERSED", name="financepayoutdeductionstatus"),
                nullable=False,
                server_default="ACTIVE",
            ),
            sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reversed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reversal_reason", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "ix_finance_payout_deductions_case_month",
            "finance_payout_deductions",
            ["case_id", "billing_month"],
        )

    if not has_table("case_finance_notes"):
        op.create_table(
            "case_finance_notes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("billing_month", sa.String(16), nullable=True),
            sa.Column(
                "note_scope",
                sa.Enum("CRM", "HR", "FINANCE", name="casefinancenotescope"),
                nullable=False,
            ),
            sa.Column(
                "note_type",
                sa.Enum(
                    "TRANSITION",
                    "RETAINER",
                    "DEDUCTION",
                    "NOTICE_PERIOD",
                    "OTHER",
                    name="casefinancenotetype",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("amount_inr", sa.Numeric(12, 2), nullable=True),
            sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column(
                "linked_deduction_id",
                sa.Integer(),
                sa.ForeignKey("finance_payout_deductions.id"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_case_finance_notes_case_id", "case_finance_notes", ["case_id"])


def downgrade() -> None:
    if has_table("case_finance_notes"):
        op.drop_index("ix_case_finance_notes_case_id", table_name="case_finance_notes")
        op.drop_table("case_finance_notes")
    if has_table("finance_payout_deductions"):
        op.drop_index("ix_finance_payout_deductions_case_month", table_name="finance_payout_deductions")
        op.drop_table("finance_payout_deductions")
    if has_table("finance_correction_proposals"):
        op.drop_index("ix_finance_correction_proposals_case_month", table_name="finance_correction_proposals")
        op.drop_table("finance_correction_proposals")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for typ in (
            "casefinancenotescope",
            "casefinancenotetype",
            "financepayoutdeductiondirection",
            "financepayoutdeductionstatus",
            "financecorrectionproposaltype",
            "financewrongside",
            "financeproposalstatus",
        ):
            op.execute(f"DROP TYPE IF EXISTS {typ}")
