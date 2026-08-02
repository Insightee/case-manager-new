"""Make monthly billing first-class on cases + safe rate migration.

Revision ID: y2z3a4b5c6d7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-02

Staging-only for this step. Do NOT run against production until Steps 2–3
are validated and finance has classified monthly_case_review rows.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from migration_util import has_column, has_table

revision: str = "y2z3a4b5c6d7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Genuine per-session rates are well below this; higher values look monthly.
_MONTHLY_LOOKING_THRESHOLD_INR = 8000


def _pg_enum_value(enum_name: str, value: str) -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def upgrade() -> None:
    _pg_enum_value("billingtype", "MONTHLY_FIXED")

    if not has_column("cases", "client_monthly_rate_inr"):
        with op.batch_alter_table("cases", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("client_monthly_rate_inr", sa.Numeric(precision=12, scale=2), nullable=True)
            )

    if not has_table("monthly_case_review"):
        op.create_table(
            "monthly_case_review",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False, index=True),
            sa.Column("client_name", sa.String(length=255), nullable=True),
            sa.Column("service_type", sa.String(length=128), nullable=True),
            sa.Column("classification_bucket", sa.String(length=32), nullable=False),
            sa.Column("previous_billing_type", sa.String(length=32), nullable=True),
            sa.Column("current_billing_type", sa.String(length=32), nullable=True),
            sa.Column(
                "previous_client_rate_per_session_inr",
                sa.Numeric(precision=12, scale=2),
                nullable=True,
            ),
            sa.Column("client_monthly_rate_inr", sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column("product_billing_rule_id", sa.Integer(), nullable=True),
            sa.Column("review_reason", sa.String(length=255), nullable=True),
            sa.Column("finance_decision", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    conn = op.get_bind()

    # Capture auto-migrate candidates before mutation (clean MONTHLY_FIXED product link).
    auto_rows = conn.execute(
        text(
            """
            SELECT
                c.id AS case_id,
                TRIM(COALESCE(ch.first_name, '') || ' ' || COALESCE(ch.last_name, '')) AS client_name,
                c.service_type,
                c.billing_type,
                c.client_rate_per_session_inr,
                c.product_billing_rule_id
            FROM cases c
            LEFT JOIN children ch ON ch.id = c.child_id
            LEFT JOIN product_billing_rules r ON r.id = c.product_billing_rule_id
            WHERE c.product_billing_rule_id IS NOT NULL
              AND r.billing_model = 'MONTHLY_FIXED'
            """
        )
    ).mappings().all()

    for row in auto_rows:
        rate = row["client_rate_per_session_inr"]
        conn.execute(
            text(
                """
                UPDATE cases
                SET billing_type = 'MONTHLY_FIXED',
                    client_monthly_rate_inr = :rate,
                    client_rate_per_session_inr = NULL
                WHERE id = :case_id
                """
            ),
            {"rate": rate, "case_id": row["case_id"]},
        )
        conn.execute(
            text(
                """
                INSERT INTO monthly_case_review (
                    case_id, client_name, service_type, classification_bucket,
                    previous_billing_type, current_billing_type,
                    previous_client_rate_per_session_inr, client_monthly_rate_inr,
                    product_billing_rule_id, review_reason, finance_decision
                ) VALUES (
                    :case_id, :client_name, :service_type, 'AUTO_MIGRATED',
                    :previous_billing_type, 'MONTHLY_FIXED',
                    :previous_rate, :monthly_rate,
                    :rule_id, 'Linked to MONTHLY_FIXED product rule', 'AUTO'
                )
                """
            ),
            {
                "case_id": row["case_id"],
                "client_name": (row["client_name"] or "").strip() or None,
                "service_type": row["service_type"],
                "previous_billing_type": row["billing_type"],
                "previous_rate": rate,
                "monthly_rate": rate,
                "rule_id": row["product_billing_rule_id"],
            },
        )

    # Review list: blank/missing rule, or non-monthly rule with monthly-looking rate.
    # Do NOT mutate these cases.
    review_rows = conn.execute(
        text(
            """
            SELECT
                c.id AS case_id,
                TRIM(COALESCE(ch.first_name, '') || ' ' || COALESCE(ch.last_name, '')) AS client_name,
                c.service_type,
                c.billing_type,
                c.client_rate_per_session_inr,
                c.product_billing_rule_id,
                CASE
                    WHEN c.product_billing_rule_id IS NULL THEN 'Missing product_billing_rule_id'
                    ELSE 'Non-monthly product rule with monthly-looking rate'
                END AS review_reason
            FROM cases c
            LEFT JOIN children ch ON ch.id = c.child_id
            LEFT JOIN product_billing_rules r ON r.id = c.product_billing_rule_id
            WHERE (
                c.product_billing_rule_id IS NULL
                AND c.client_rate_per_session_inr IS NOT NULL
                AND c.client_rate_per_session_inr > :threshold
            )
            OR (
                c.product_billing_rule_id IS NOT NULL
                AND (r.billing_model IS NULL OR r.billing_model <> 'MONTHLY_FIXED')
                AND c.client_rate_per_session_inr IS NOT NULL
                AND c.client_rate_per_session_inr > :threshold
            )
            """
        ),
        {"threshold": _MONTHLY_LOOKING_THRESHOLD_INR},
    ).mappings().all()

    for row in review_rows:
        conn.execute(
            text(
                """
                INSERT INTO monthly_case_review (
                    case_id, client_name, service_type, classification_bucket,
                    previous_billing_type, current_billing_type,
                    previous_client_rate_per_session_inr, client_monthly_rate_inr,
                    product_billing_rule_id, review_reason, finance_decision
                ) VALUES (
                    :case_id, :client_name, :service_type, 'NEEDS_REVIEW',
                    :previous_billing_type, :current_billing_type,
                    :previous_rate, NULL,
                    :rule_id, :review_reason, NULL
                )
                """
            ),
            {
                "case_id": row["case_id"],
                "client_name": (row["client_name"] or "").strip() or None,
                "service_type": row["service_type"],
                "previous_billing_type": row["billing_type"],
                "current_billing_type": row["billing_type"],
                "previous_rate": row["client_rate_per_session_inr"],
                "rule_id": row["product_billing_rule_id"],
                "review_reason": row["review_reason"],
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    if has_table("monthly_case_review"):
        auto_rows = conn.execute(
            text(
                """
                SELECT case_id, previous_billing_type, previous_client_rate_per_session_inr
                FROM monthly_case_review
                WHERE classification_bucket = 'AUTO_MIGRATED'
                """
            )
        ).mappings().all()
        for row in auto_rows:
            conn.execute(
                text(
                    """
                    UPDATE cases
                    SET billing_type = :billing_type,
                        client_rate_per_session_inr = :rate,
                        client_monthly_rate_inr = NULL
                    WHERE id = :case_id
                    """
                ),
                {
                    "billing_type": row["previous_billing_type"],
                    "rate": row["previous_client_rate_per_session_inr"],
                    "case_id": row["case_id"],
                },
            )
        op.drop_table("monthly_case_review")

    if has_column("cases", "client_monthly_rate_inr"):
        with op.batch_alter_table("cases", schema=None) as batch_op:
            batch_op.drop_column("client_monthly_rate_inr")
    # Postgres cannot remove enum values safely; MONTHLY_FIXED remains on billingtype.
