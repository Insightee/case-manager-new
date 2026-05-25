"""Portal API query hardening: audit case_id and composite indexes.

Revision ID: c4d5e6f7a8b9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_column, has_table

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("audit_events") and not has_column("audit_events", "case_id"):
        with op.batch_alter_table("audit_events") as batch_op:
            batch_op.add_column(sa.Column("case_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_audit_events_case_id",
                "cases",
                ["case_id"],
                ["id"],
            )

    create_index_if_missing("ix_audit_events_case_id_created_id", "audit_events", ["case_id", "created_at", "id"])
    create_index_if_missing("ix_audit_events_entity_type_id", "audit_events", ["entity_type", "entity_id"])
    create_index_if_missing("ix_audit_events_created_id", "audit_events", ["created_at", "id"])

    create_index_if_missing(
        "ix_sessions_therapist_scheduled",
        "sessions",
        ["therapist_user_id", "scheduled_date"],
    )
    create_index_if_missing(
        "ix_sessions_therapist_status",
        "sessions",
        ["therapist_user_id", "status"],
    )
    create_index_if_missing(
        "ix_sessions_case_scheduled",
        "sessions",
        ["case_id", "scheduled_date"],
    )
    create_index_if_missing(
        "ix_monthly_reports_therapist_status",
        "monthly_reports",
        ["therapist_user_id", "status"],
    )
    create_index_if_missing(
        "ix_monthly_reports_case_month",
        "monthly_reports",
        ["case_id", "month"],
    )
    create_index_if_missing(
        "ix_therapist_slots_therapist_date_status",
        "therapist_slots",
        ["therapist_user_id", "slot_date", "status"],
    )
    create_index_if_missing(
        "ix_therapist_slots_case_date_status",
        "therapist_slots",
        ["case_id", "slot_date", "status"],
    )
    create_index_if_missing(
        "ix_attachments_case_entity_type",
        "attachments",
        ["case_id", "entity_type"],
    )


def downgrade() -> None:
    for name, table in [
        ("ix_attachments_case_entity_type", "attachments"),
        ("ix_therapist_slots_case_date_status", "therapist_slots"),
        ("ix_therapist_slots_therapist_date_status", "therapist_slots"),
        ("ix_monthly_reports_case_month", "monthly_reports"),
        ("ix_monthly_reports_therapist_status", "monthly_reports"),
        ("ix_sessions_case_scheduled", "sessions"),
        ("ix_sessions_therapist_status", "sessions"),
        ("ix_sessions_therapist_scheduled", "sessions"),
        ("ix_audit_events_created_id", "audit_events"),
        ("ix_audit_events_entity_type_id", "audit_events"),
        ("ix_audit_events_case_id_created_id", "audit_events"),
    ]:
        if has_table(table):
            try:
                op.drop_index(name, table_name=table)
            except Exception:
                pass
    if has_table("audit_events") and has_column("audit_events", "case_id"):
        with op.batch_alter_table("audit_events") as batch_op:
            try:
                batch_op.drop_constraint("fk_audit_events_case_id", type_="foreignkey")
            except Exception:
                pass
            batch_op.drop_column("case_id")
