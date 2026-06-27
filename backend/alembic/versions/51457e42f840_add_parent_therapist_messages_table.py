"""add parent therapist messages table

Revision ID: 51457e42f840
Revises: d0b7effca6df
Create Date: 2026-06-27 13:11:55.456333

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '51457e42f840'
down_revision: Union[str, None] = 'd0b7effca6df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("parent_therapist_messages"):
        op.create_table(
            "parent_therapist_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("attachment_path", sa.String(length=512), nullable=True),
            sa.Column("attachment_name", sa.String(length=255), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        )
        op.create_index("ix_parent_therapist_messages_case_id", "parent_therapist_messages", ["case_id"])
        op.create_index("ix_parent_therapist_messages_sender_id", "parent_therapist_messages", ["sender_id"])
        op.create_index("ix_parent_therapist_messages_recipient_id", "parent_therapist_messages", ["recipient_id"])
        op.create_index("ix_parent_therapist_messages_created_at", "parent_therapist_messages", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("parent_therapist_messages"):
        op.drop_index("ix_parent_therapist_messages_created_at", table_name="parent_therapist_messages")
        op.drop_index("ix_parent_therapist_messages_recipient_id", table_name="parent_therapist_messages")
        op.drop_index("ix_parent_therapist_messages_sender_id", table_name="parent_therapist_messages")
        op.drop_index("ix_parent_therapist_messages_case_id", table_name="parent_therapist_messages")
        op.drop_table("parent_therapist_messages")
