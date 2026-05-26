"""Leave policy: billing_category, service_line, profile backfill fields.

Revision ID: v5w6x7y8z9a0
Revises: u4v5w6x7y8z9
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v5w6x7y8z9a0"
down_revision: Union[str, None] = "u4v5w6x7y8z9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("therapist_leaves", sa.Column("service_line", sa.String(length=64), nullable=True))
    op.add_column(
        "therapist_leaves",
        sa.Column(
            "billing_category",
            sa.Enum("PAID", "UNPAID", "CARRY_FORWARD", name="leavebillingcategory"),
            nullable=True,
        ),
    )
    op.create_index("ix_therapist_leaves_service_line", "therapist_leaves", ["service_line"])

    op.add_column("therapist_profiles", sa.Column("employment_start_date", sa.Date(), nullable=True))
    op.add_column("therapist_profiles", sa.Column("leave_balance_year", sa.Integer(), nullable=True))
    op.add_column(
        "therapist_profiles",
        sa.Column("leave_paid_days_backfill", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "therapist_profiles",
        sa.Column("leave_carry_forward_days_backfill", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("therapist_profiles", sa.Column("leave_backfill_note", sa.Text(), nullable=True))
    op.add_column("therapist_profiles", sa.Column("leave_backfill_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("therapist_profiles", sa.Column("leave_backfill_updated_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_therapist_profiles_leave_backfill_updated_by",
        "therapist_profiles",
        "users",
        ["leave_backfill_updated_by_user_id"],
        ["id"],
    )

    from app.services.leave_backfill_service import run_backfill_on_connection

    run_backfill_on_connection(op.get_bind())


def downgrade() -> None:
    op.drop_constraint("fk_therapist_profiles_leave_backfill_updated_by", "therapist_profiles", type_="foreignkey")
    op.drop_column("therapist_profiles", "leave_backfill_updated_by_user_id")
    op.drop_column("therapist_profiles", "leave_backfill_updated_at")
    op.drop_column("therapist_profiles", "leave_backfill_note")
    op.drop_column("therapist_profiles", "leave_carry_forward_days_backfill")
    op.drop_column("therapist_profiles", "leave_paid_days_backfill")
    op.drop_column("therapist_profiles", "leave_balance_year")
    op.drop_column("therapist_profiles", "employment_start_date")
    op.drop_index("ix_therapist_leaves_service_line", table_name="therapist_leaves")
    op.drop_column("therapist_leaves", "billing_category")
    op.drop_column("therapist_leaves", "service_line")
    op.execute(sa.text("DROP TYPE IF EXISTS leavebillingcategory"))
