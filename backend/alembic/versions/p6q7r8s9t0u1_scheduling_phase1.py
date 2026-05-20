"""scheduling phase1: slot statuses, recurring assignments, reschedules

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("recurring_schedule_assignments"):
        op.create_table(
            "recurring_schedule_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("therapist_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("service_type", sa.String(64), nullable=True),
            sa.Column("product_module", sa.String(64), nullable=True),
            sa.Column("weekdays_json", sa.Text(), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=False),
            sa.Column("end_time", sa.Time(), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("recurrence_group_id", sa.String(36), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column(
                "status",
                sa.Enum("ACTIVE", "CANCELLED", name="recurringschedulestatus"),
                nullable=False,
                server_default="ACTIVE",
            ),
            sa.Column("booked_slot_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
        )
        op.create_index("ix_recurring_schedule_case_id", "recurring_schedule_assignments", ["case_id"])
        op.create_index(
            "ix_recurring_schedule_group_id", "recurring_schedule_assignments", ["recurrence_group_id"]
        )

    if not has_table("appointment_reschedules"):
        op.create_table(
            "appointment_reschedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("therapist_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("from_slot_id", sa.Integer(), sa.ForeignKey("therapist_slots.id"), nullable=False),
            sa.Column("to_slot_id", sa.Integer(), sa.ForeignKey("therapist_slots.id"), nullable=False),
            sa.Column("from_session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("to_session_id", sa.Integer(), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("requested_by_role", sa.String(32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
        )
        op.create_index("ix_appointment_reschedules_case_id", "appointment_reschedules", ["case_id"])

    with op.batch_alter_table("therapist_slots") as batch_op:
        if not has_column("therapist_slots", "rescheduled_to_slot_id"):
            batch_op.add_column(sa.Column("rescheduled_to_slot_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_slot_rescheduled_to", "therapist_slots", ["rescheduled_to_slot_id"], ["id"]
            )
        if not has_column("therapist_slots", "cancelled_at"):
            batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        if not has_column("therapist_slots", "cancelled_by_user_id"):
            batch_op.add_column(sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_slot_cancelled_by", "users", ["cancelled_by_user_id"], ["id"]
            )
        if not has_column("therapist_slots", "cancellation_reason"):
            batch_op.add_column(sa.Column("cancellation_reason", sa.Text(), nullable=True))
        if not has_column("therapist_slots", "updated_at"):
            batch_op.add_column(
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.text("(CURRENT_TIMESTAMP)"),
                    nullable=True,
                )
            )


def downgrade() -> None:
    if has_table("appointment_reschedules"):
        op.drop_table("appointment_reschedules")
    if has_table("recurring_schedule_assignments"):
        op.drop_table("recurring_schedule_assignments")
    with op.batch_alter_table("therapist_slots") as batch_op:
        for col in ("updated_at", "cancellation_reason", "cancelled_by_user_id", "cancelled_at", "rescheduled_to_slot_id"):
            if has_column("therapist_slots", col):
                batch_op.drop_column(col)
