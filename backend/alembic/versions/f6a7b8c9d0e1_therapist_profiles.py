"""therapist_profiles

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-21 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "therapist_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("short_bio", sa.Text(), nullable=True),
        sa.Column("academic_qualifications", sa.Text(), nullable=True),
        sa.Column("professional_certificates", sa.JSON(), nullable=True),
        sa.Column("services_offered", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PENDING", "APPROVED", "PAUSED", name="therapistprofilestatus"),
            nullable=False,
        ),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_therapist_profiles_user_id", "therapist_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_therapist_profiles_user_id", table_name="therapist_profiles")
    op.drop_table("therapist_profiles")
