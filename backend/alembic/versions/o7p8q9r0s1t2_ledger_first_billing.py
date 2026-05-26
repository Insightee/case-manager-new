"""ledger-first billing: product rules, billing ledger, orgs

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o7p8q9r0s1t2"
down_revision: Union[str, None] = "n6o7p8q9r0s1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_enum_value(enum_name: str, value: str) -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def upgrade() -> None:
    for v in ("MONTHLY_FIXED", "B2B", "MANUAL"):
        _pg_enum_value("clientinvoicetype", v)
    _pg_enum_value("clientinvoicestatus", "VOID")
    _pg_enum_value("carepackagestatus", "PENDING_PAYMENT")

    op.create_table(
        "organisations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("gstin", sa.String(length=32), nullable=True),
        sa.Column("billing_address", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "product_billing_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=128), nullable=False),
        sa.Column("product_category", sa.String(length=64), nullable=False),
        sa.Column("product_module", sa.String(length=64), nullable=False),
        sa.Column(
            "billing_model",
            sa.Enum(
                "POSTPAID_PER_SESSION",
                "PREPAID_PACKAGE",
                "MONTHLY_FIXED",
                name="productbillingmodel",
            ),
            nullable=False,
        ),
        sa.Column("default_rate_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("monthly_fee_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("package_sessions", sa.Integer(), nullable=True),
        sa.Column("package_validity_days", sa.Integer(), nullable=True),
        sa.Column("gst_applicable", sa.Boolean(), nullable=True),
        sa.Column("gst_rate_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("hsn_sac_code", sa.String(length=16), nullable=True),
        sa.Column("payment_terms", sa.String(length=64), nullable=True),
        sa.Column("client_no_show_billable", sa.Boolean(), nullable=True),
        sa.Column("therapist_cancel_billable", sa.Boolean(), nullable=True),
        sa.Column("included_paid_leaves", sa.Integer(), nullable=True),
        sa.Column("unpaid_leave_deduction_method", sa.String(length=64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_billing_rules_product_module", "product_billing_rules", ["product_module"])
    op.create_index("ix_product_billing_rules_active", "product_billing_rules", ["active"])

    op.add_column("cases", sa.Column("product_billing_rule_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_cases_product_billing_rule",
        "cases",
        "product_billing_rules",
        ["product_billing_rule_id"],
        ["id"],
    )
    op.create_index("ix_cases_product_billing_rule_id", "cases", ["product_billing_rule_id"])

    op.create_table(
        "billing_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("parent_user_id", sa.Integer(), nullable=True),
        sa.Column("therapist_user_id", sa.Integer(), nullable=True),
        sa.Column("product_billing_rule_id", sa.Integer(), nullable=True),
        sa.Column(
            "source_type",
            sa.Enum(
                "SESSION",
                "DAILY_LOG",
                "LEAVE",
                "MANUAL",
                "MONTHLY_FEE",
                "PACKAGE_PURCHASE",
                "PACKAGE_CONSUMPTION",
                name="ledgersourcetype",
            ),
            nullable=False,
        ),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("daily_log_id", sa.Integer(), nullable=True),
        sa.Column("ledger_month", sa.String(length=32), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "SESSION_COMPLETED",
                "SESSION_CANCELLED",
                "CLIENT_NO_SHOW",
                "THERAPIST_CANCEL",
                "MONTHLY_FEE",
                "LEAVE_DEDUCTION",
                "PACKAGE_CONSUMPTION",
                "MANUAL_ADJUSTMENT",
                name="ledgereventtype",
            ),
            nullable=False,
        ),
        sa.Column(
            "billable_status",
            sa.Enum(
                "PENDING_REVIEW",
                "BILLABLE",
                "NON_BILLABLE",
                "INVOICED",
                "EXCLUDED",
                name="billablestatus",
            ),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(8, 2), nullable=True),
        sa.Column("rate_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("amount_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("gst_rate_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("gst_amount_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("hsn_sac_code", sa.String(length=16), nullable=True),
        sa.Column("total_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("payout_amount_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("insighte_margin_inr", sa.Numeric(12, 2), nullable=True),
        sa.Column("client_invoice_id", sa.Integer(), nullable=True),
        sa.Column("care_package_id", sa.Integer(), nullable=True),
        sa.Column(
            "dispute_status",
            sa.Enum("NONE", "OPEN", "RESOLVED", name="ledgerdisputestatus"),
            nullable=True,
        ),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("overridden_by_user_id", sa.Integer(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_billing_rule_id"], ["product_billing_rules.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.ForeignKeyConstraint(["daily_log_id"], ["daily_logs.id"]),
        sa.ForeignKeyConstraint(["client_invoice_id"], ["client_invoices.id"]),
        sa.ForeignKeyConstraint(["care_package_id"], ["care_packages.id"]),
        sa.ForeignKeyConstraint(["overridden_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_billing_ledger_case_id", "billing_ledger", ["case_id"])
    op.create_index("ix_billing_ledger_ledger_month", "billing_ledger", ["ledger_month"])
    op.create_index("ix_billing_ledger_billable_status", "billing_ledger", ["billable_status"])

    op.add_column("client_invoices", sa.Column("approved_by_user_id", sa.Integer(), nullable=True))
    op.add_column("client_invoices", sa.Column("payment_policy_snapshot", sa.Text(), nullable=True))
    op.add_column("client_invoices", sa.Column("organisation_id", sa.Integer(), nullable=True))
    op.add_column("client_invoices", sa.Column("purchase_order_ref", sa.String(length=64), nullable=True))
    op.add_column("client_invoices", sa.Column("contract_ref", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        "fk_client_invoices_approved_by",
        "client_invoices",
        "users",
        ["approved_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_client_invoices_organisation",
        "client_invoices",
        "organisations",
        ["organisation_id"],
        ["id"],
    )

    op.add_column("client_invoice_lines", sa.Column("billing_ledger_id", sa.Integer(), nullable=True))
    op.add_column("client_invoice_lines", sa.Column("gst_rate_percent", sa.Numeric(5, 2), nullable=True))
    op.add_column("client_invoice_lines", sa.Column("gst_amount_inr", sa.Numeric(12, 2), nullable=True))
    op.add_column("client_invoice_lines", sa.Column("hsn_sac_code", sa.String(length=16), nullable=True))
    op.add_column("client_invoice_lines", sa.Column("taxable_amount_inr", sa.Numeric(12, 2), nullable=True))
    op.create_foreign_key(
        "fk_client_invoice_lines_billing_ledger",
        "client_invoice_lines",
        "billing_ledger",
        ["billing_ledger_id"],
        ["id"],
    )

    op.add_column("care_packages", sa.Column("product_billing_rule_id", sa.Integer(), nullable=True))
    op.add_column("care_packages", sa.Column("client_invoice_id", sa.Integer(), nullable=True))
    op.add_column("care_packages", sa.Column("valid_from", sa.Date(), nullable=True))
    op.add_column("care_packages", sa.Column("amount_inr", sa.Numeric(12, 2), nullable=True))
    op.create_foreign_key(
        "fk_care_packages_product_rule",
        "care_packages",
        "product_billing_rules",
        ["product_billing_rule_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_care_packages_client_invoice",
        "care_packages",
        "client_invoices",
        ["client_invoice_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_care_packages_client_invoice", "care_packages", type_="foreignkey")
    op.drop_constraint("fk_care_packages_product_rule", "care_packages", type_="foreignkey")
    op.drop_column("care_packages", "amount_inr")
    op.drop_column("care_packages", "valid_from")
    op.drop_column("care_packages", "client_invoice_id")
    op.drop_column("care_packages", "product_billing_rule_id")

    op.drop_constraint("fk_client_invoice_lines_billing_ledger", "client_invoice_lines", type_="foreignkey")
    op.drop_column("client_invoice_lines", "taxable_amount_inr")
    op.drop_column("client_invoice_lines", "hsn_sac_code")
    op.drop_column("client_invoice_lines", "gst_amount_inr")
    op.drop_column("client_invoice_lines", "gst_rate_percent")
    op.drop_column("client_invoice_lines", "billing_ledger_id")

    op.drop_constraint("fk_client_invoices_organisation", "client_invoices", type_="foreignkey")
    op.drop_constraint("fk_client_invoices_approved_by", "client_invoices", type_="foreignkey")
    op.drop_column("client_invoices", "contract_ref")
    op.drop_column("client_invoices", "purchase_order_ref")
    op.drop_column("client_invoices", "organisation_id")
    op.drop_column("client_invoices", "payment_policy_snapshot")
    op.drop_column("client_invoices", "approved_by_user_id")

    op.drop_index("ix_billing_ledger_billable_status", table_name="billing_ledger")
    op.drop_index("ix_billing_ledger_ledger_month", table_name="billing_ledger")
    op.drop_index("ix_billing_ledger_case_id", table_name="billing_ledger")
    op.drop_table("billing_ledger")

    op.drop_constraint("fk_cases_product_billing_rule", "cases", type_="foreignkey")
    op.drop_index("ix_cases_product_billing_rule_id", table_name="cases")
    op.drop_column("cases", "product_billing_rule_id")

    op.drop_index("ix_product_billing_rules_active", table_name="product_billing_rules")
    op.drop_index("ix_product_billing_rules_product_module", table_name="product_billing_rules")
    op.drop_table("product_billing_rules")
    op.drop_table("organisations")
