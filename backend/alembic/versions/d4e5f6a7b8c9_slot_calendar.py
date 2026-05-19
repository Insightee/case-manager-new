"""slot_calendar_booking

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-20 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    with op.batch_alter_table("therapist_slots") as batch_op:
        batch_op.add_column(sa.Column("case_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("booked_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "booking_source",
                sa.Enum("THERAPIST", "ADMIN", "PARENT", "SYSTEM", name="bookingsource"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("recurrence_group_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("slot_duration_minutes", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_slot_case", "cases", ["case_id"], ["id"])
        batch_op.create_foreign_key("fk_slot_booked_by", "users", ["booked_by_user_id"], ["id"])
        batch_op.create_index("ix_therapist_slots_recurrence_group_id", ["recurrence_group_id"])
        batch_op.create_unique_constraint("uq_therapist_slot_datetime", ["therapist_user_id", "slot_date", "start_time"])


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
