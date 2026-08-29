"""Phase 3 shared availability and Google calendar.

Revision ID: s2t3u4v5w6x7
Revises: r1s2t3u4v5w6
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "s2t3u4v5w6x7"
down_revision: Union[str, None] = "r1s2t3u4v5w6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("staff_availability_rules"):
        op.create_table(
            "staff_availability_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("weekday", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("effective_from", sa.Date(), nullable=True),
            sa.Column("effective_to", sa.Date(), nullable=True),
            sa.Column("slot_granularity_minutes", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index(
            "ix_staff_availability_rules_user_id",
            "staff_availability_rules",
            ["user_id"],
        )
        op.create_index(
            "ix_staff_availability_rules_weekday",
            "staff_availability_rules",
            ["weekday"],
        )
        op.create_index(
            "ix_staff_availability_rules_effective_from",
            "staff_availability_rules",
            ["effective_from"],
        )
        op.create_index(
            "ix_staff_availability_rules_effective_to",
            "staff_availability_rules",
            ["effective_to"],
        )

    if not has_table("staff_availability_exceptions"):
        op.create_table(
            "staff_availability_exceptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column(
                "type",
                sa.Enum("CLOSED", "CUSTOM", name="availabilityexceptiontype"),
                nullable=False,
                server_default="CLOSED",
            ),
            sa.Column("start_time", sa.Time(), nullable=True),
            sa.Column("end_time", sa.Time(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "date", "type", "start_time", "end_time", name="uq_staff_availability_exceptions"),
        )
        op.create_index(
            "ix_staff_availability_exceptions_user_id",
            "staff_availability_exceptions",
            ["user_id"],
        )
        op.create_index(
            "ix_staff_availability_exceptions_date",
            "staff_availability_exceptions",
            ["date"],
        )

    if not has_table("staff_booking_policy"):
        op.create_table(
            "staff_booking_policy",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("min_notice_minutes", sa.Integer(), nullable=False, server_default="120"),
            sa.Column("max_days_ahead", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("allowed_durations_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_staff_booking_policy_user_id",
            "staff_booking_policy",
            ["user_id"],
            unique=True,
        )

    if not has_table("user_calendar_connections"):
        op.create_table(
            "user_calendar_connections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="google"),
            sa.Column("google_account_email", sa.String(length=255), nullable=True),
            sa.Column("access_token_encrypted", sa.Text(), nullable=True),
            sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("freebusy_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("last_sync_ok_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("user_id", "provider", name="uq_user_calendar_connections_user_provider"),
        )
        op.create_index(
            "ix_user_calendar_connections_user_id",
            "user_calendar_connections",
            ["user_id"],
        )
        op.create_index(
            "ix_user_calendar_connections_provider",
            "user_calendar_connections",
            ["provider"],
        )


def downgrade() -> None:
    if has_table("user_calendar_connections"):
        op.drop_index("ix_user_calendar_connections_provider", table_name="user_calendar_connections")
        op.drop_index("ix_user_calendar_connections_user_id", table_name="user_calendar_connections")
        op.drop_table("user_calendar_connections")
    if has_table("staff_booking_policy"):
        op.drop_index("ix_staff_booking_policy_user_id", table_name="staff_booking_policy")
        op.drop_table("staff_booking_policy")
    if has_table("staff_availability_exceptions"):
        op.drop_index("ix_staff_availability_exceptions_date", table_name="staff_availability_exceptions")
        op.drop_index("ix_staff_availability_exceptions_user_id", table_name="staff_availability_exceptions")
        op.drop_table("staff_availability_exceptions")
    if has_table("staff_availability_rules"):
        op.drop_index("ix_staff_availability_rules_effective_to", table_name="staff_availability_rules")
        op.drop_index("ix_staff_availability_rules_effective_from", table_name="staff_availability_rules")
        op.drop_index("ix_staff_availability_rules_weekday", table_name="staff_availability_rules")
        op.drop_index("ix_staff_availability_rules_user_id", table_name="staff_availability_rules")
        op.drop_table("staff_availability_rules")
    op.execute("DROP TYPE IF EXISTS availabilityexceptiontype")

