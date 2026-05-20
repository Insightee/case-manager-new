"""scale indexes and invite_tokens table

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_table

revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("invite_tokens"):
        op.create_table(
            "invite_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("role_name", sa.String(64), nullable=False),
            sa.Column("module_assignments", sa.JSON(), nullable=True),
            sa.Column("token", sa.String(128), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("linked_child_id", sa.Integer(), sa.ForeignKey("children.id"), nullable=True),
        )

    create_index_if_missing("ix_cases_child_id", "cases", ["child_id"])
    create_index_if_missing("ix_cases_status", "cases", ["status"])
    create_index_if_missing("ix_cases_product_module", "cases", ["product_module"])
    create_index_if_missing("ix_cases_case_manager_user_id", "cases", ["case_manager_user_id"])
    create_index_if_missing("ix_cases_status_product_module", "cases", ["status", "product_module"])

    create_index_if_missing(
        "ix_case_assignments_therapist_status",
        "case_assignments",
        ["therapist_user_id", "status"],
    )
    create_index_if_missing(
        "ix_case_assignments_case_status",
        "case_assignments",
        ["case_id", "status"],
    )

    if has_table("daily_logs"):
        create_index_if_missing(
            "ix_daily_logs_approval_visibility_submitted",
            "daily_logs",
            ["approval_status", "visibility_status", "submitted_at"],
        )

    if has_table("support_tickets"):
        create_index_if_missing("ix_support_tickets_case_id", "support_tickets", ["case_id"])
        create_index_if_missing("ix_support_tickets_raised_by", "support_tickets", ["raised_by_user_id"])
        create_index_if_missing("ix_support_tickets_status_created", "support_tickets", ["status", "created_at"])

    if has_table("ticket_messages"):
        create_index_if_missing("ix_ticket_messages_ticket_id", "ticket_messages", ["ticket_id"])

    if has_table("incidents"):
        create_index_if_missing("ix_incidents_case_id", "incidents", ["case_id"])
        create_index_if_missing("ix_incidents_created_at", "incidents", ["created_at"])

    if has_table("notifications"):
        create_index_if_missing("ix_notifications_user_read", "notifications", ["user_id", "is_read"])


def downgrade() -> None:
    for name, table in [
        ("ix_notifications_user_read", "notifications"),
        ("ix_incidents_created_at", "incidents"),
        ("ix_incidents_case_id", "incidents"),
        ("ix_ticket_messages_ticket_id", "ticket_messages"),
        ("ix_support_tickets_status_created", "support_tickets"),
        ("ix_support_tickets_raised_by", "support_tickets"),
        ("ix_support_tickets_case_id", "support_tickets"),
        ("ix_daily_logs_approval_visibility_submitted", "daily_logs"),
        ("ix_case_assignments_case_status", "case_assignments"),
        ("ix_case_assignments_therapist_status", "case_assignments"),
        ("ix_cases_status_product_module", "cases"),
        ("ix_cases_case_manager_user_id", "cases"),
        ("ix_cases_product_module", "cases"),
        ("ix_cases_status", "cases"),
        ("ix_cases_child_id", "cases"),
    ]:
        if has_table(table):
            try:
                op.drop_index(name, table_name=table)
            except Exception:
                pass
