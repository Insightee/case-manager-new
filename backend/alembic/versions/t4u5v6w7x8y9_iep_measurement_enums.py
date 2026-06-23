"""IEP unified measurement enum columns on session evidence.

Revision ID: t4u5v6w7x8y9
Revises: s2t3u4v5w6x7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column

revision: str = "t4u5v6w7x8y9"
down_revision: Union[str, None] = "s2t3u4v5w6x7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_col(table: str, col: sa.Column) -> None:
    if not has_column(table, col.name):
        op.add_column(table, col)


def upgrade() -> None:
    _add_col("session_goal_entries", sa.Column("participation", sa.String(64), nullable=True))
    _add_col("session_goal_entries", sa.Column("independence_support_needed", sa.String(64), nullable=True))
    _add_col("session_goal_entries", sa.Column("goal_achievement", sa.String(64), nullable=True))
    _add_col("strategy_use_events", sa.Column("participation", sa.String(64), nullable=True))
    _add_col("strategy_use_events", sa.Column("independence_support_needed", sa.String(64), nullable=True))
    _add_col("strategy_use_events", sa.Column("goal_achievement", sa.String(64), nullable=True))


def downgrade() -> None:
    for table, col in [
        ("session_goal_entries", "participation"),
        ("session_goal_entries", "independence_support_needed"),
        ("session_goal_entries", "goal_achievement"),
        ("strategy_use_events", "participation"),
        ("strategy_use_events", "independence_support_needed"),
        ("strategy_use_events", "goal_achievement"),
    ]:
        if has_column(table, col):
            op.drop_column(table, col)
