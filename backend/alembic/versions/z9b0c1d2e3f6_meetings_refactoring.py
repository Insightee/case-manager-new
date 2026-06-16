"""meetings refactoring

Revision ID: z9b0c1d2e3f6
Revises: z9b0c1d2e3f5
Create Date: 2026-06-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from migration_util import has_column, has_table

revision: str = "z9b0c1d2e3f6"
down_revision: Union[str, None] = "z9b0c1d2e3f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to case_manager_meetings
    with op.batch_alter_table("case_manager_meetings", schema=None) as batch_op:
        if not has_column("case_manager_meetings", "other_reason"):
            batch_op.add_column(sa.Column("other_reason", sa.String(length=255), nullable=True))
        if not has_column("case_manager_meetings", "platform"):
            batch_op.add_column(sa.Column("platform", sa.String(length=50), nullable=True))
        if not has_column("case_manager_meetings", "rescheduled_from_id"):
            batch_op.add_column(sa.Column("rescheduled_from_id", sa.Integer(), sa.ForeignKey("case_manager_meetings.id"), nullable=True))
        if not has_column("case_manager_meetings", "reschedule_reason"):
            batch_op.add_column(sa.Column("reschedule_reason", sa.Text(), nullable=True))
        if not has_column("case_manager_meetings", "notes_outcome"):
            batch_op.add_column(sa.Column("notes_outcome", sa.String(length=50), nullable=True))
        if not has_column("case_manager_meetings", "notes_summary"):
            batch_op.add_column(sa.Column("notes_summary", sa.Text(), nullable=True))
        if not has_column("case_manager_meetings", "notes_next_meeting_required"):
            batch_op.add_column(sa.Column("notes_next_meeting_required", sa.Boolean(), nullable=False, server_default=sa.false()))
        if not has_column("case_manager_meetings", "notes_additional"):
            batch_op.add_column(sa.Column("notes_additional", sa.Text(), nullable=True))
        if not has_column("case_manager_meetings", "mentor_user_id"):
            batch_op.add_column(sa.Column("mentor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
        if not has_column("case_manager_meetings", "linked_observation_report_id"):
            batch_op.add_column(sa.Column("linked_observation_report_id", sa.Integer(), sa.ForeignKey("observation_reports.id"), nullable=True))
        if not has_column("case_manager_meetings", "linked_observation_checklist_id"):
            batch_op.add_column(sa.Column("linked_observation_checklist_id", sa.Integer(), sa.ForeignKey("observation_checklists.id"), nullable=True))
        if not has_column("case_manager_meetings", "linked_iep_id"):
            batch_op.add_column(sa.Column("linked_iep_id", sa.Integer(), sa.ForeignKey("iep_plans.id"), nullable=True))
        if not has_column("case_manager_meetings", "linked_monthly_report_id"):
            batch_op.add_column(sa.Column("linked_monthly_report_id", sa.Integer(), sa.ForeignKey("monthly_reports.id"), nullable=True))
        if not has_column("case_manager_meetings", "linked_incident_id"):
            batch_op.add_column(sa.Column("linked_incident_id", sa.Integer(), sa.ForeignKey("incidents.id"), nullable=True))
        if not has_column("case_manager_meetings", "linked_ticket_id"):
            batch_op.add_column(sa.Column("linked_ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id"), nullable=True))

    # 2. Create meeting_actions table
    if not has_table("meeting_actions"):
        op.create_table(
            "meeting_actions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("case_manager_meetings.id"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("owner_role", sa.String(length=50), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    if has_table("meeting_actions"):
        op.drop_table("meeting_actions")

    with op.batch_alter_table("case_manager_meetings", schema=None) as batch_op:
        if has_column("case_manager_meetings", "linked_ticket_id"):
            batch_op.drop_column("linked_ticket_id")
        if has_column("case_manager_meetings", "linked_incident_id"):
            batch_op.drop_column("linked_incident_id")
        if has_column("case_manager_meetings", "linked_monthly_report_id"):
            batch_op.drop_column("linked_monthly_report_id")
        if has_column("case_manager_meetings", "linked_iep_id"):
            batch_op.drop_column("linked_iep_id")
        if has_column("case_manager_meetings", "linked_observation_checklist_id"):
            batch_op.drop_column("linked_observation_checklist_id")
        if has_column("case_manager_meetings", "linked_observation_report_id"):
            batch_op.drop_column("linked_observation_report_id")
        if has_column("case_manager_meetings", "mentor_user_id"):
            batch_op.drop_column("mentor_user_id")
        if has_column("case_manager_meetings", "notes_additional"):
            batch_op.drop_column("notes_additional")
        if has_column("case_manager_meetings", "notes_next_meeting_required"):
            batch_op.drop_column("notes_next_meeting_required")
        if has_column("case_manager_meetings", "notes_summary"):
            batch_op.drop_column("notes_summary")
        if has_column("case_manager_meetings", "notes_outcome"):
            batch_op.drop_column("notes_outcome")
        if has_column("case_manager_meetings", "reschedule_reason"):
            batch_op.drop_column("reschedule_reason")
        if has_column("case_manager_meetings", "rescheduled_from_id"):
            batch_op.drop_column("rescheduled_from_id")
        if has_column("case_manager_meetings", "platform"):
            batch_op.drop_column("platform")
        if has_column("case_manager_meetings", "other_reason"):
            batch_op.drop_column("other_reason")
