"""Additive: billing_readiness_exception_rules (configurable master-sheet exception gates).

Revision ID: d0e1f2a3b4c6
Revises: c9d0e1f2a3b5
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "d0e1f2a3b4c6"
down_revision: Union[str, None] = "c9d0e1f2a3b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_RULES: list[tuple[str, float, str, str]] = [
    ("SESSION_COUNT_MISMATCH", 0, "WARN", "Session count on raised invoice vs ledger/sessions activity"),
    ("LEAVE_MISMATCH", 0, "WARN", "Leave count on raised invoice vs ledger leave events"),
    ("INVOICE_ENGINE_AMOUNT_MISMATCH", 1, "BLOCK", "Raised client invoice total vs composer engine output (INR)"),
    ("MISSING_INVOICE_NUMBER", 0, "WARN", "Active case-month without a client invoice number"),
    ("REPORTS_NOT_SUBMITTED", 0, "WARN", "Monthly report not approved/published for billed month"),
    ("STATUS_CONFLICT", 0, "BLOCK", "Terminated/on-break case status with billable activity present"),
]


def upgrade() -> None:
    if not has_table("billing_readiness_exception_rules"):
        op.create_table(
            "billing_readiness_exception_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "exception_type",
                sa.Enum(
                    "SESSION_COUNT_MISMATCH",
                    "LEAVE_MISMATCH",
                    "INVOICE_ENGINE_AMOUNT_MISMATCH",
                    "MISSING_INVOICE_NUMBER",
                    "REPORTS_NOT_SUBMITTED",
                    "STATUS_CONFLICT",
                    name="billingreadinessexceptiontype",
                ),
                nullable=False,
                unique=True,
            ),
            sa.Column("tolerance", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
            sa.Column(
                "severity",
                sa.Enum("WARN", "BLOCK", name="billingreadinessexceptionseverity"),
                nullable=False,
                server_default="WARN",
            ),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "ix_billing_readiness_exception_rules_type",
            "billing_readiness_exception_rules",
            ["exception_type"],
            unique=True,
        )

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for exc_type, tolerance, severity, description in _DEFAULT_RULES:
        bind.execute(
            sa.text(
                """
                INSERT INTO billing_readiness_exception_rules
                    (exception_type, tolerance, severity, active, description)
                SELECT CAST(:exc_type AS billingreadinessexceptiontype),
                       :tolerance,
                       CAST(:severity AS billingreadinessexceptionseverity),
                       true,
                       :description
                WHERE NOT EXISTS (
                    SELECT 1 FROM billing_readiness_exception_rules
                    WHERE exception_type = CAST(:exc_type AS billingreadinessexceptiontype)
                )
                """
            ),
            {
                "exc_type": exc_type,
                "tolerance": tolerance,
                "severity": severity,
                "description": description,
            },
        )


def downgrade() -> None:
    if has_table("billing_readiness_exception_rules"):
        op.drop_index("ix_billing_readiness_exception_rules_type", table_name="billing_readiness_exception_rules")
        op.drop_table("billing_readiness_exception_rules")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS billingreadinessexceptiontype")
        op.execute("DROP TYPE IF EXISTS billingreadinessexceptionseverity")
