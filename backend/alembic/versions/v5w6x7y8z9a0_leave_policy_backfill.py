"""Leave policy: billing_category, service_line, profile backfill fields.

Revision ID: v5w6x7y8z9a0
Revises: u4v5w6x7y8z9
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "v5w6x7y8z9a0"
down_revision: Union[str, None] = "u4v5w6x7y8z9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE leavebillingcategory AS ENUM ('PAID', 'UNPAID', 'CARRY_FORWARD');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
    billing_enum = postgresql.ENUM(
        "PAID",
        "UNPAID",
        "CARRY_FORWARD",
        name="leavebillingcategory",
        create_type=False,
    )

    leave_cols = (
        {c["name"] for c in insp.get_columns("therapist_leaves")} if insp.has_table("therapist_leaves") else set()
    )
    if "service_line" not in leave_cols:
        op.add_column("therapist_leaves", sa.Column("service_line", sa.String(length=64), nullable=True))
    if "billing_category" not in leave_cols:
        op.add_column("therapist_leaves", sa.Column("billing_category", billing_enum, nullable=True))
    if not insp.has_index("therapist_leaves", "ix_therapist_leaves_service_line"):
        op.create_index("ix_therapist_leaves_service_line", "therapist_leaves", ["service_line"])

    profile_cols = (
        {c["name"] for c in insp.get_columns("therapist_profiles")} if insp.has_table("therapist_profiles") else set()
    )
    if "employment_start_date" not in profile_cols:
        op.add_column("therapist_profiles", sa.Column("employment_start_date", sa.Date(), nullable=True))
    if "leave_balance_year" not in profile_cols:
        op.add_column("therapist_profiles", sa.Column("leave_balance_year", sa.Integer(), nullable=True))
    if "leave_paid_days_backfill" not in profile_cols:
        op.add_column(
            "therapist_profiles",
            sa.Column("leave_paid_days_backfill", sa.Integer(), nullable=False, server_default="0"),
        )
    if "leave_carry_forward_days_backfill" not in profile_cols:
        op.add_column(
            "therapist_profiles",
            sa.Column("leave_carry_forward_days_backfill", sa.Integer(), nullable=False, server_default="0"),
        )
    if "leave_backfill_note" not in profile_cols:
        op.add_column("therapist_profiles", sa.Column("leave_backfill_note", sa.Text(), nullable=True))
    if "leave_backfill_updated_at" not in profile_cols:
        op.add_column(
            "therapist_profiles", sa.Column("leave_backfill_updated_at", sa.DateTime(timezone=True), nullable=True)
        )
    if "leave_backfill_updated_by_user_id" not in profile_cols:
        op.add_column("therapist_profiles", sa.Column("leave_backfill_updated_by_user_id", sa.Integer(), nullable=True))
    fk_names = {fk["name"] for fk in insp.get_foreign_keys("therapist_profiles")} if insp.has_table("therapist_profiles") else set()
    if "fk_therapist_profiles_leave_backfill_updated_by" not in fk_names:
        op.create_foreign_key(
            "fk_therapist_profiles_leave_backfill_updated_by",
            "therapist_profiles",
            "users",
            ["leave_backfill_updated_by_user_id"],
            ["id"],
        )

    from app.services.leave_backfill_service import run_backfill_on_connection

    run_backfill_on_connection(bind)


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
