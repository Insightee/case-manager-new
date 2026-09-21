"""Staff attendance and staff leave tables."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "st1ff4tt3nd1"
down_revision: Union[str, None] = "op1n2o3t4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _leave_status_column():
    """Reuse existing leavestatus enum from therapist_leaves (do not CREATE TYPE again)."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            "PENDING",
            "APPROVED",
            "REJECTED",
            "CANCELLED",
            name="leavestatus",
            create_type=False,
        )
    return sa.Enum("PENDING", "APPROVED", "REJECTED", "CANCELLED", name="leavestatus")


def upgrade() -> None:
    op.create_table(
        "staff_attendance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("entry_type", sa.Enum("LIVE", "FORGOT", name="staffattendanceentrytype"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("IN_PROGRESS", "COMPLETED", "AUTO_CLOSED", name="staffattendancestatus"),
            nullable=False,
        ),
        sa.Column("work_summary", sa.Text(), nullable=True),
        sa.Column("forgot_reason", sa.Text(), nullable=True),
        sa.Column("manual_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manual_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_work_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_break_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_paused", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("auto_closed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "work_date", "entry_type", name="uq_staff_attendance_user_day_type"),
    )
    op.create_index("ix_staff_attendance_user_id", "staff_attendance", ["user_id"])
    op.create_index("ix_staff_attendance_work_date", "staff_attendance", ["work_date"])

    op.create_table(
        "staff_attendance_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attendance_id", sa.Integer(), nullable=False),
        sa.Column("segment_type", sa.Enum("WORK", "BREAK", name="staffattendancesegmenttype"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attendance_id"], ["staff_attendance.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_attendance_segments_attendance_id", "staff_attendance_segments", ["attendance_id"])

    op.create_table(
        "staff_leaves",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_user_id", sa.Integer(), nullable=False),
        sa.Column("leave_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", _leave_status_column(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_leaves_staff_user_id", "staff_leaves", ["staff_user_id"])
    op.create_index("ix_staff_leaves_leave_date", "staff_leaves", ["leave_date"])


def downgrade() -> None:
    op.drop_index("ix_staff_leaves_leave_date", table_name="staff_leaves")
    op.drop_index("ix_staff_leaves_staff_user_id", table_name="staff_leaves")
    op.drop_table("staff_leaves")
    op.drop_index("ix_staff_attendance_segments_attendance_id", table_name="staff_attendance_segments")
    op.drop_table("staff_attendance_segments")
    op.drop_index("ix_staff_attendance_work_date", table_name="staff_attendance")
    op.drop_index("ix_staff_attendance_user_id", table_name="staff_attendance")
    op.drop_table("staff_attendance")
    op.execute("DROP TYPE IF EXISTS staffattendancesegmenttype")
    op.execute("DROP TYPE IF EXISTS staffattendancestatus")
    op.execute("DROP TYPE IF EXISTS staffattendanceentrytype")
