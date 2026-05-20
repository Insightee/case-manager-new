"""parent session feedback and ticket topics/escalation

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("daily_logs", "parent_session_rating"):
        with op.batch_alter_table("daily_logs", schema=None) as batch_op:
            batch_op.add_column(sa.Column("parent_session_rating", sa.Integer(), nullable=True))
    if not _has_column("daily_logs", "parent_feedback"):
        with op.batch_alter_table("daily_logs", schema=None) as batch_op:
            batch_op.add_column(sa.Column("parent_feedback", sa.Text(), nullable=True))
    if not _has_column("daily_logs", "parent_feedback_at"):
        with op.batch_alter_table("daily_logs", schema=None) as batch_op:
            batch_op.add_column(sa.Column("parent_feedback_at", sa.DateTime(timezone=True), nullable=True))

    if not _has_column("support_tickets", "topic"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "topic",
                    sa.Enum(
                        "BILLING_PAYMENT",
                        "THERAPIST",
                        "CASE_MANAGER",
                        "OTHER",
                        name="tickettopic",
                    ),
                    nullable=False,
                    server_default="OTHER",
                )
            )
    if not _has_column("support_tickets", "escalation_level"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.add_column(sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="0"))
    if not _has_column("support_tickets", "parent_satisfaction_rating"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.add_column(sa.Column("parent_satisfaction_rating", sa.Integer(), nullable=True))
    if not _has_column("support_tickets", "parent_resolution_feedback"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.add_column(sa.Column("parent_resolution_feedback", sa.Text(), nullable=True))
    if not _has_column("support_tickets", "resolved_at"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))

    if op.get_bind().dialect.has_table(op.get_bind(), "invite_tokens"):
        if not _has_column("invite_tokens", "linked_child_id"):
            with op.batch_alter_table("invite_tokens", schema=None) as batch_op:
                batch_op.add_column(sa.Column("linked_child_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    if op.get_bind().dialect.has_table(op.get_bind(), "invite_tokens"):
        if _has_column("invite_tokens", "linked_child_id"):
            with op.batch_alter_table("invite_tokens", schema=None) as batch_op:
                batch_op.drop_column("linked_child_id")

    if _has_column("support_tickets", "resolved_at"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.drop_column("resolved_at")
    if _has_column("support_tickets", "parent_resolution_feedback"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.drop_column("parent_resolution_feedback")
    if _has_column("support_tickets", "parent_satisfaction_rating"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.drop_column("parent_satisfaction_rating")
    if _has_column("support_tickets", "escalation_level"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.drop_column("escalation_level")
    if _has_column("support_tickets", "topic"):
        with op.batch_alter_table("support_tickets", schema=None) as batch_op:
            batch_op.drop_column("topic")

    if _has_column("daily_logs", "parent_feedback_at"):
        with op.batch_alter_table("daily_logs", schema=None) as batch_op:
            batch_op.drop_column("parent_feedback_at")
    if _has_column("daily_logs", "parent_feedback"):
        with op.batch_alter_table("daily_logs", schema=None) as batch_op:
            batch_op.drop_column("parent_feedback")
    if _has_column("daily_logs", "parent_session_rating"):
        with op.batch_alter_table("daily_logs", schema=None) as batch_op:
            batch_op.drop_column("parent_session_rating")
