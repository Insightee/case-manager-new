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
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("daily_logs"):
        return
    cols = {c["name"] for c in insp.get_columns("daily_logs")}
    if "late_addition" not in cols:
        op.add_column(
            "daily_logs",
            sa.Column("late_addition", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "late_reason" not in cols:
        op.add_column("daily_logs", sa.Column("late_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("daily_logs"):
        return
    cols = {c["name"] for c in insp.get_columns("daily_logs")}
    if "late_reason" in cols:
        op.drop_column("daily_logs", "late_reason")
    if "late_addition" in cols:
        op.drop_column("daily_logs", "late_addition")
