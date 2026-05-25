"""invoice_billing_breakdown

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-19 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_index, has_table

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_case_column(name: str, column: sa.Column) -> None:
    if not has_column("cases", name):
        with op.batch_alter_table("cases") as batch_op:
            batch_op.add_column(column)


def _add_invoice_column(name: str, column: sa.Column) -> None:
    if not has_column("invoices", name):
        with op.batch_alter_table("invoices") as batch_op:
            batch_op.add_column(column)


def upgrade() -> None:
    _add_case_column(
        "billing_type",
        sa.Column("billing_type", sa.Enum("PER_SESSION", "PACKAGE", name="billingtype"), nullable=True),
    )
    _add_case_column("client_rate_per_session_inr", sa.Column("client_rate_per_session_inr", sa.Numeric(12, 2), nullable=True))
    _add_case_column("package_session_count", sa.Column("package_session_count", sa.Integer(), nullable=True))
    _add_case_column("package_amount_inr", sa.Column("package_amount_inr", sa.Numeric(12, 2), nullable=True))
    _add_case_column(
        "compensation_mode",
        sa.Column("compensation_mode", sa.Enum("PERCENTAGE", "FIXED_LUMP", name="compensationmode"), nullable=True),
    )
    _add_case_column("pay_share_pct", sa.Column("pay_share_pct", sa.Numeric(5, 2), nullable=True))
    _add_case_column("therapist_fixed_pay_inr", sa.Column("therapist_fixed_pay_inr", sa.Numeric(12, 2), nullable=True))
    _add_case_column("billing_notes", sa.Column("billing_notes", sa.Text(), nullable=True))
    _add_case_column("billing_updated_at", sa.Column("billing_updated_at", sa.DateTime(timezone=True), nullable=True))
    _add_case_column("billing_updated_by_user_id", sa.Column("billing_updated_by_user_id", sa.Integer(), nullable=True))

    _add_invoice_column("subtotal_inr", sa.Column("subtotal_inr", sa.Numeric(12, 2), nullable=True))
    _add_invoice_column(
        "leave_deduction_inr",
        sa.Column("leave_deduction_inr", sa.Numeric(12, 2), nullable=True, server_default="0"),
    )
    _add_invoice_column(
        "adjustment_inr",
        sa.Column("adjustment_inr", sa.Numeric(12, 2), nullable=True, server_default="0"),
    )
    _add_invoice_column("notes", sa.Column("notes", sa.Text(), nullable=True))

    if not has_table("invoice_case_lines"):
        op.create_table(
        "invoice_case_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("case_code", sa.String(32), nullable=False),
        sa.Column("billing_type", sa.String(32), nullable=False),
        sa.Column("included_sessions", sa.Integer(), server_default="0"),
        sa.Column("additional_sessions", sa.Integer(), server_default="0"),
        sa.Column("therapist_share_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("billing_snapshot", sa.JSON(), nullable=True),
        )
    if has_table("invoice_case_lines") and not has_index("invoice_case_lines", "ix_invoice_case_lines_invoice_id"):
        op.create_index("ix_invoice_case_lines_invoice_id", "invoice_case_lines", ["invoice_id"])

    if not has_table("invoice_session_lines"):
        op.create_table(
        "invoice_session_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_case_line_id", sa.Integer(), sa.ForeignKey("invoice_case_lines.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("daily_log_id", sa.Integer(), sa.ForeignKey("daily_logs.id"), nullable=True),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), server_default="60"),
        sa.Column("line_type", sa.Enum("INCLUDED", "ADDITIONAL", "PER_SESSION", name="sessionlinetype"), nullable=False),
        sa.Column("amount_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("source", sa.Enum("LOG", "MANUAL_LATE", "ADJUSTMENT", name="sessionlinesource"), nullable=False),
        sa.Column("included", sa.Boolean(), server_default="1"),
        sa.Column("flags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    if has_table("invoice_session_lines") and not has_index(
        "invoice_session_lines", "ix_invoice_session_lines_case_line_id"
    ):
        op.create_index("ix_invoice_session_lines_case_line_id", "invoice_session_lines", ["invoice_case_line_id"])


def downgrade() -> None:
    op.drop_table("invoice_session_lines")
    op.drop_table("invoice_case_lines")
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_column("notes")
        batch_op.drop_column("adjustment_inr")
        batch_op.drop_column("leave_deduction_inr")
        batch_op.drop_column("subtotal_inr")
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("billing_updated_by_user_id")
        batch_op.drop_column("billing_updated_at")
        batch_op.drop_column("billing_notes")
        batch_op.drop_column("therapist_fixed_pay_inr")
        batch_op.drop_column("pay_share_pct")
        batch_op.drop_column("compensation_mode")
        batch_op.drop_column("package_amount_inr")
        batch_op.drop_column("package_session_count")
        batch_op.drop_column("client_rate_per_session_inr")
        batch_op.drop_column("billing_type")
