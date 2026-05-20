"""case_manager_meetings table

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, None] = "t0u1v2w3x4y5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_manager_meetings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("case_manager_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True, index=True),
        sa.Column("parent_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("therapist_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("scheduled_date", sa.Date(), nullable=False, index=True),
        sa.Column("scheduled_time", sa.Time(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "meeting_type",
            sa.Enum("CLIENT_ONLY", "CLIENT_AND_THERAPIST", "SUPERVISION", name="meetingtype"),
            nullable=False,
            server_default="CLIENT_ONLY",
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("notes_concerns", sa.Text(), nullable=True),
        sa.Column("notes_follow_up", sa.Text(), nullable=True),
        sa.Column("notes_action", sa.Text(), nullable=True),
        sa.Column("notes_other", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("SCHEDULED", "COMPLETED", "CANCELLED", name="meetingstatus"),
            nullable=False,
            server_default="SCHEDULED",
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("case_manager_meetings")
    op.execute("DROP TYPE IF EXISTS meetingtype")
    op.execute("DROP TYPE IF EXISTS meetingstatus")
