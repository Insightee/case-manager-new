"""client billing hub — invoices, packages, payments, disputes

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(length=32), nullable=False),
        sa.Column("parent_user_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("invoice_type", sa.Enum("PREPAID", "POSTPAID", name="clientinvoicetype"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "GENERATED",
                "SENT",
                "PARTIALLY_PAID",
                "PAID",
                "OVERDUE",
                "DISPUTED",
                "CANCELLED",
                name="clientinvoicestatus",
            ),
            nullable=False,
        ),
        sa.Column("billing_month", sa.String(length=32), nullable=False),
        sa.Column("service_type", sa.String(length=128), nullable=False),
        sa.Column("product_module", sa.String(length=64), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("subtotal_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("discount_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("package_deduction_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("adjustment_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_paid_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index("ix_client_invoices_parent_user_id", "client_invoices", ["parent_user_id"])
    op.create_index("ix_client_invoices_case_id", "client_invoices", ["case_id"])
    op.create_index("ix_client_invoices_billing_month", "client_invoices", ["billing_month"])

    op.create_table(
        "client_invoice_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_invoice_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("daily_log_id", sa.Integer(), nullable=True),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("therapist_name", sa.String(length=128), nullable=False),
        sa.Column("service_label", sa.String(length=128), nullable=False),
        sa.Column("session_status", sa.String(length=64), nullable=False),
        sa.Column("amount_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("package_deducted", sa.Boolean(), nullable=True),
        sa.Column("parent_summary", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["client_invoice_id"], ["client_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["daily_log_id"], ["daily_logs.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_invoice_lines_invoice_id", "client_invoice_lines", ["client_invoice_id"])

    op.create_table(
        "care_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("parent_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("total_sessions", sa.Integer(), nullable=False),
        sa.Column("used_sessions", sa.Integer(), nullable=True),
        sa.Column("validity_end", sa.Date(), nullable=True),
        sa.Column("service_label", sa.String(length=128), nullable=True),
        sa.Column("status", sa.Enum("ACTIVE", "EXPIRED", "EXHAUSTED", name="carepackagestatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "client_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.Enum("UPI", "BANK_TRANSFER", "CASH", "CHEQUE", "GATEWAY", name="paymentmethod"), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("recorded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["client_invoice_id"], ["client_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "billing_disputes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_invoice_id", sa.Integer(), nullable=False),
        sa.Column("client_invoice_line_id", sa.Integer(), nullable=True),
        sa.Column("parent_user_id", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("OPEN", "UNDER_REVIEW", "RESOLVED", "REJECTED", name="billingdisputestatus"),
            nullable=False,
        ),
        sa.Column("admin_resolution", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_invoice_id"], ["client_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_invoice_line_id"], ["client_invoice_lines.id"]),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("billing_disputes")
    op.drop_table("client_payments")
    op.drop_table("care_packages")
    op.drop_index("ix_client_invoice_lines_invoice_id", table_name="client_invoice_lines")
    op.drop_table("client_invoice_lines")
    op.drop_index("ix_client_invoices_billing_month", table_name="client_invoices")
    op.drop_index("ix_client_invoices_case_id", table_name="client_invoices")
    op.drop_index("ix_client_invoices_parent_user_id", table_name="client_invoices")
    op.drop_table("client_invoices")
