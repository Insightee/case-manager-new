"""query efficiency indexes

Revision ID: v1a2b3c4d5e6
Revises: u7v8w9x0y1z2
Create Date: 2026-05-28 13:08:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "v1a2b3c4d5e6"
down_revision = "u7v8w9x0y1z2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_notifications_user_read_created",
        "notifications",
        ["user_id", "is_read", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_sessions_therapist_date_status",
        "sessions",
        ["therapist_user_id", "scheduled_date", "status"],
        unique=False,
    )
    op.create_index(
        "ix_slots_therapist_date_status",
        "therapist_slots",
        ["therapist_user_id", "slot_date", "status"],
        unique=False,
    )
    op.create_index(
        "ix_daily_logs_submitted_status",
        "daily_logs",
        ["submitted_at", "approval_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_daily_logs_submitted_status", table_name="daily_logs")
    op.drop_index("ix_slots_therapist_date_status", table_name="therapist_slots")
    op.drop_index("ix_sessions_therapist_date_status", table_name="sessions")
    op.drop_index("ix_notifications_user_read_created", table_name="notifications")
