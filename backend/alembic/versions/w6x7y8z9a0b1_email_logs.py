"""email_logs table for transactional email audit

Revision ID: w6x7y8z9a0b1
Revises: v5w6x7y8z9a0
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w6x7y8z9a0b1"
down_revision: Union[str, None] = "v5w6x7y8z9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("recipient_role", sa.String(length=64), nullable=True),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("template_key", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="smtp"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_logs_event_type", "email_logs", ["event_type"])
    op.create_index("ix_email_logs_recipient_email", "email_logs", ["recipient_email"])
    op.create_index("ix_email_logs_status", "email_logs", ["status"])
    op.create_index(
        "ix_email_logs_recipient_created",
        "email_logs",
        ["recipient_email", "created_at"],
    )
    op.create_index(
        "ix_email_logs_event_status",
        "email_logs",
        ["event_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_logs_event_status", table_name="email_logs")
    op.drop_index("ix_email_logs_recipient_created", table_name="email_logs")
    op.drop_index("ix_email_logs_status", table_name="email_logs")
    op.drop_index("ix_email_logs_recipient_email", table_name="email_logs")
    op.drop_index("ix_email_logs_event_type", table_name="email_logs")
    op.drop_table("email_logs")
