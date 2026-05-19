"""profile_session_logs

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-22 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("avatar_path", sa.String(512), nullable=True))

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("actual_start_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("actual_end_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("auto_ended", sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table("daily_logs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("session_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("goals_addressed", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("follow_ups", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_logs", schema=None) as batch_op:
        batch_op.drop_column("follow_ups")
        batch_op.drop_column("goals_addressed")
        batch_op.drop_column("session_notes")

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("auto_ended")
        batch_op.drop_column("actual_end_at")
        batch_op.drop_column("actual_start_at")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("avatar_path")
