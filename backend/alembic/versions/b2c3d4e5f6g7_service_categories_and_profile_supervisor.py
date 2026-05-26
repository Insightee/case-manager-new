"""Add service_categories table and supervisor/mentor to therapist_profiles

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEED_CATEGORIES = [
    ("shadow", "Shadow support", 0),
    ("homecare", "Homecare", 1),
    ("occupational_therapy", "Occupational therapy", 2),
    ("speech_therapy", "Speech therapy", 3),
    ("special_educator", "Special educator", 4),
    ("behavior_therapy", "Behavior therapy", 5),
    ("play_therapy", "Play therapy", 6),
    ("customised_employment", "Customised employment", 7),
    ("subject_tutor", "Subject tutor", 8),
    ("sports", "Sports", 9),
    ("counselling", "Counselling", 10),
]


def upgrade() -> None:
    op.create_table(
        "service_categories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.bulk_insert(
        sa.table(
            "service_categories",
            sa.column("id", sa.String),
            sa.column("label", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [{"id": sid, "label": label, "sort_order": order} for sid, label, order in _SEED_CATEGORIES],
    )

    op.add_column(
        "therapist_profiles",
        sa.Column("supervisor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "therapist_profiles",
        sa.Column("mentor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("therapist_profiles", "mentor_user_id")
    op.drop_column("therapist_profiles", "supervisor_user_id")
    op.drop_table("service_categories")
