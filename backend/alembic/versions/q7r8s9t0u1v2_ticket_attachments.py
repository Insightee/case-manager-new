"""ticket attachments table

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("ticket_attachments"):
        op.create_table(
            "ticket_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id"), nullable=False),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("ticket_messages.id"), nullable=True),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_path", sa.String(512), nullable=False),
            sa.Column("mime_type", sa.String(128), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"])
        op.create_index("ix_ticket_attachments_message_id", "ticket_attachments", ["message_id"])


def downgrade() -> None:
    if has_table("ticket_attachments"):
        op.drop_table("ticket_attachments")
