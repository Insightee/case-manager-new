"""late_addition_daily_logs

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-19 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("daily_logs") as batch_op:
        batch_op.add_column(sa.Column("late_addition", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("late_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_logs") as batch_op:
        batch_op.drop_column("late_reason")
        batch_op.drop_column("late_addition")
