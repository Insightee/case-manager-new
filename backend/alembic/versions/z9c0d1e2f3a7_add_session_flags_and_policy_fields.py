"""Add session cancellation_reason, data_quality_flag; billing rule absence policy fields.

Revision ID: z9c0d1e2f3a7
Revises: d0b7effca6df
Create Date: 2026-06-24
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "z9c0d1e2f3a7"
down_revision: Union[str, None] = "d0b7effca6df"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PR1+PR2 — session flags
    op.add_column("sessions", sa.Column("cancellation_reason", sa.String(64), nullable=True))
    op.add_column("sessions", sa.Column("data_quality_flag", sa.String(64), nullable=True))

    # PR3 — billing rule absence policy fields
    op.add_column(
        "product_billing_rules",
        sa.Column("child_absent_therapist_payable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "product_billing_rules",
        sa.Column("package_consumes_on_child_absent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # PR3 — idempotency constraint on billing_ledger
    op.create_index(
        "ix_billing_ledger_source_event_unique",
        "billing_ledger",
        ["source_type", "source_id", "event_type"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_billing_ledger_source_event_unique", table_name="billing_ledger")
    op.drop_column("product_billing_rules", "package_consumes_on_child_absent")
    op.drop_column("product_billing_rules", "child_absent_therapist_payable")
    op.drop_column("sessions", "data_quality_flag")
    op.drop_column("sessions", "cancellation_reason")
