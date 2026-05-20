"""appointment booking policy and session slot link

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_appointment_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("reschedules_used", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("case_id", "year", "month", name="uq_case_appointment_usage_month"),
    )
    op.create_index("ix_case_appointment_usage_case_id", "case_appointment_usage", ["case_id"])

    with op.batch_alter_table("case_assignments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "booking_mode",
                sa.String(length=16),
                server_default="OPEN",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("fixed_weekdays", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fixed_start_time", sa.Time(), nullable=True))
        batch_op.add_column(sa.Column("fixed_end_time", sa.Time(), nullable=True))
        batch_op.add_column(sa.Column("fixed_recurrence_group_id", sa.String(length=36), nullable=True))

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("slot_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_sessions_slot_id", "therapist_slots", ["slot_id"], ["id"])

    with op.batch_alter_table("therapist_slots", schema=None) as batch_op:
        batch_op.add_column(sa.Column("session_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_therapist_slots_session_id", "sessions", ["session_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("therapist_slots", schema=None) as batch_op:
        batch_op.drop_constraint("fk_therapist_slots_session_id", type_="foreignkey")
        batch_op.drop_column("session_id")

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_sessions_slot_id", type_="foreignkey")
        batch_op.drop_column("slot_id")

    with op.batch_alter_table("case_assignments", schema=None) as batch_op:
        batch_op.drop_column("fixed_recurrence_group_id")
        batch_op.drop_column("fixed_end_time")
        batch_op.drop_column("fixed_start_time")
        batch_op.drop_column("fixed_weekdays")
        batch_op.drop_column("booking_mode")

    op.drop_index("ix_case_appointment_usage_case_id", table_name="case_appointment_usage")
    op.drop_table("case_appointment_usage")
