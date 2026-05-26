"""Billing composer: line item fields, gateway flags, case billing preferences."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "t2u3v4w5x6y7"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_invoices", sa.Column("gateway_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("client_invoices", sa.Column("gateway_payment_url", sa.String(length=512), nullable=True))
    op.add_column("client_invoice_lines", sa.Column("line_item_type", sa.String(length=32), nullable=True))
    op.add_column("client_invoice_lines", sa.Column("quantity", sa.Numeric(10, 2), nullable=True))
    op.add_column("client_invoice_lines", sa.Column("unit_rate_inr", sa.Numeric(12, 2), nullable=True))
    op.add_column("client_invoice_lines", sa.Column("finance_note", sa.Text(), nullable=True))
    op.add_column("client_invoice_lines", sa.Column("therapist_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_client_invoice_lines_therapist_user",
        "client_invoice_lines",
        "users",
        ["therapist_user_id"],
        ["id"],
    )
    op.create_table(
        "case_billing_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False, unique=True),
        sa.Column("invoice_type", sa.String(length=32), nullable=True),
        sa.Column("gst_applicable", sa.Boolean(), nullable=True),
        sa.Column("gst_rate_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("gateway_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("due_date_offset_days", sa.Integer(), nullable=True),
        sa.Column("payment_policy_template", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("case_billing_preferences")
    op.drop_constraint("fk_client_invoice_lines_therapist_user", "client_invoice_lines", type_="foreignkey")
    op.drop_column("client_invoice_lines", "therapist_user_id")
    op.drop_column("client_invoice_lines", "finance_note")
    op.drop_column("client_invoice_lines", "unit_rate_inr")
    op.drop_column("client_invoice_lines", "quantity")
    op.drop_column("client_invoice_lines", "line_item_type")
    op.drop_column("client_invoices", "gateway_payment_url")
    op.drop_column("client_invoices", "gateway_enabled")
