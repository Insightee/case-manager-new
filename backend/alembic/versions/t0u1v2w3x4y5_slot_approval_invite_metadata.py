"""slot approval_status, leave_block_leave_id, invite invite_metadata

Revision ID: t0u1v2w3x4y5
Revises: r8s9t0u1v2w3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column

revision: str = "t0u1v2w3x4y5"
down_revision: Union[str, None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("invite_tokens", "invite_metadata"):
        with op.batch_alter_table("invite_tokens") as batch_op:
            batch_op.add_column(sa.Column("invite_metadata", sa.JSON(), nullable=True))

    if not has_column("therapist_slots", "approval_status"):
        with op.batch_alter_table("therapist_slots") as batch_op:
            batch_op.add_column(
                sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="CONFIRMED")
            )
    if not has_column("therapist_slots", "leave_block_leave_id"):
        with op.batch_alter_table("therapist_slots") as batch_op:
            batch_op.add_column(sa.Column("leave_block_leave_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    if has_column("therapist_slots", "leave_block_leave_id"):
        with op.batch_alter_table("therapist_slots") as batch_op:
            batch_op.drop_column("leave_block_leave_id")
    if has_column("therapist_slots", "approval_status"):
        with op.batch_alter_table("therapist_slots") as batch_op:
            batch_op.drop_column("approval_status")
    if has_column("invite_tokens", "invite_metadata"):
        with op.batch_alter_table("invite_tokens") as batch_op:
            batch_op.drop_column("invite_metadata")
