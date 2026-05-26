"""slot_calendar_booking

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-20 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_index, has_table

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("therapist_schedule_templates"):
        op.create_table(
            "therapist_schedule_templates",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("therapist_user_id", sa.Integer(), nullable=False),
            sa.Column("config_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
            sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("therapist_user_id"),
        )
    if has_table("therapist_slots"):
        if not has_column("therapist_slots", "case_id"):
            op.add_column("therapist_slots", sa.Column("case_id", sa.Integer(), nullable=True))
        if not has_column("therapist_slots", "booked_by_user_id"):
            op.add_column("therapist_slots", sa.Column("booked_by_user_id", sa.Integer(), nullable=True))
        if not has_column("therapist_slots", "booking_source"):
            op.add_column(
                "therapist_slots",
                sa.Column(
                    "booking_source",
                    sa.Enum("THERAPIST", "ADMIN", "PARENT", "SYSTEM", name="bookingsource"),
                    nullable=True,
                ),
            )
        if not has_column("therapist_slots", "recurrence_group_id"):
            op.add_column("therapist_slots", sa.Column("recurrence_group_id", sa.String(length=36), nullable=True))
        if not has_column("therapist_slots", "slot_duration_minutes"):
            op.add_column("therapist_slots", sa.Column("slot_duration_minutes", sa.Integer(), nullable=True))
        # FK/index/unique constraints may already exist from create_all; skip if present
        if not has_index("therapist_slots", "ix_therapist_slots_recurrence_group_id"):
            op.create_index("ix_therapist_slots_recurrence_group_id", "therapist_slots", ["recurrence_group_id"])


def downgrade() -> None:
    with op.batch_alter_table("therapist_slots") as batch_op:
        batch_op.drop_constraint("uq_therapist_slot_datetime", type_="unique")
        batch_op.drop_index("ix_therapist_slots_recurrence_group_id")
        batch_op.drop_constraint("fk_slot_booked_by", type_="foreignkey")
        batch_op.drop_constraint("fk_slot_case", type_="foreignkey")
        batch_op.drop_column("slot_duration_minutes")
        batch_op.drop_column("recurrence_group_id")
        batch_op.drop_column("booking_source")
        batch_op.drop_column("booked_by_user_id")
        batch_op.drop_column("case_id")
    op.drop_table("therapist_schedule_templates")
