"""Step 2: period-charge ledger support — retainer fields, PENDING_FINANCE, flags.

Revision ID: z3a4b5c6d7e8
Revises: y2z3a4b5c6d7
Create Date: 2026-08-02

Staging only for this step. Do NOT run against production until Steps 2–3
are validated together at cutover.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from migration_util import has_column, has_table

revision: str = "z3a4b5c6d7e8"
down_revision: Union[str, None] = "y2z3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_enum_value(enum_name: str, value: str) -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def upgrade() -> None:
    _pg_enum_value("billablestatus", "PENDING_FINANCE")

    with op.batch_alter_table("cases", schema=None) as batch_op:
        if not has_column("cases", "retainer_start_date"):
            batch_op.add_column(sa.Column("retainer_start_date", sa.Date(), nullable=True))
        if not has_column("cases", "retainer_end_date"):
            batch_op.add_column(sa.Column("retainer_end_date", sa.Date(), nullable=True))
        if not has_column("cases", "retainer_rate_inr"):
            batch_op.add_column(
                sa.Column("retainer_rate_inr", sa.Numeric(precision=12, scale=2), nullable=True)
            )

    if not has_table("billing_period_flags"):
        op.create_table(
            "billing_period_flags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("ledger_month", sa.String(length=32), nullable=False),
            sa.Column(
                "flag_kind",
                sa.Enum("ACTIVE_NO_SESSIONS", name="periodflagkind"),
                nullable=False,
            ),
            sa.Column("case_status", sa.String(length=32), nullable=True),
            sa.Column("session_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("message", sa.String(length=255), nullable=False),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_billing_period_flags_case_id", "billing_period_flags", ["case_id"])
        op.create_index("ix_billing_period_flags_ledger_month", "billing_period_flags", ["ledger_month"])


def downgrade() -> None:
    if has_table("billing_period_flags"):
        op.drop_table("billing_period_flags")
        conn = op.get_bind()
        if conn.dialect.name == "postgresql":
            op.execute(text("DROP TYPE IF EXISTS periodflagkind"))

    with op.batch_alter_table("cases", schema=None) as batch_op:
        if has_column("cases", "retainer_rate_inr"):
            batch_op.drop_column("retainer_rate_inr")
        if has_column("cases", "retainer_end_date"):
            batch_op.drop_column("retainer_end_date")
        if has_column("cases", "retainer_start_date"):
            batch_op.drop_column("retainer_start_date")
    # Postgres cannot remove PENDING_FINANCE from billablestatus safely; leave it.
