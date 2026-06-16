"""memo_management_module

Revision ID: 9585b848844d
Revises: z9b0c1d2e3f6
Create Date: 2026-06-16 14:12:41.188103

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_util import has_table

revision: str = '9585b848844d'
down_revision: Union[str, None] = 'z9b0c1d2e3f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop legacy/existing tables first to avoid conflicts
    if has_table("memo_audit_logs"):
        op.drop_table("memo_audit_logs")
    if has_table("memo_attachments"):
        op.drop_table("memo_attachments")
    if has_table("memo_messages"):
        op.drop_table("memo_messages")
    if has_table("memos"):
        op.drop_table("memos")

    # Create new memos table
    op.create_table(
        "memos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("memo_code", sa.String(length=32), nullable=False, unique=True, index=True),
        sa.Column("from_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("reply_required", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("acknowledgement_only", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, index=True, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create memo_messages table
    op.create_table(
        "memo_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("memo_id", sa.Integer(), sa.ForeignKey("memos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create memo_attachments table
    op.create_table(
        "memo_attachments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("memo_id", sa.Integer(), sa.ForeignKey("memos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("memo_messages.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create memo_audit_logs table
    op.create_table(
        "memo_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("memo_id", sa.Integer(), sa.ForeignKey("memos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("memo_audit_logs")
    op.drop_table("memo_attachments")
    op.drop_table("memo_messages")
    op.drop_table("memos")
