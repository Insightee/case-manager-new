"""session absence requests

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_absence_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "absence_type",
            sa.Enum("THERAPIST_LEAVE", "CLIENT_ABSENT", name="sessionabsencetype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING_APPROVAL", "APPROVED", "REJECTED", name="sessionabsencestatus"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("leave_billing_category", sa.String(length=32), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("billing_outcome", sa.Text(), nullable=True),
        sa.Column("therapist_leave_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.ForeignKeyConstraint(["therapist_leave_id"], ["therapist_leaves.id"]),
        sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_absence_requests_session_id", "session_absence_requests", ["session_id"])
    op.create_index("ix_session_absence_requests_case_id", "session_absence_requests", ["case_id"])
    op.create_index("ix_session_absence_requests_therapist_user_id", "session_absence_requests", ["therapist_user_id"])
    op.create_index("ix_session_absence_requests_status", "session_absence_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_session_absence_requests_status", table_name="session_absence_requests")
    op.drop_index("ix_session_absence_requests_therapist_user_id", table_name="session_absence_requests")
    op.drop_index("ix_session_absence_requests_case_id", table_name="session_absence_requests")
    op.drop_index("ix_session_absence_requests_session_id", table_name="session_absence_requests")
    op.drop_table("session_absence_requests")
