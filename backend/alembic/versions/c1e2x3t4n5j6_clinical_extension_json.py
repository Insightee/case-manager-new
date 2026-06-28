"""Clinical extension JSON on session evidence rows.

Revision ID: c1e2x3t4n5j6
Revises: t4u5v6w7x8y9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column

revision: str = "c1e2x3t4n5j6"
down_revision: Union[str, None] = "t4u5v6w7x8y9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_col(table: str, col: sa.Column) -> None:
    if not has_column(table, col.name):
        op.add_column(table, col)


def upgrade() -> None:
    _add_col("session_goal_entries", sa.Column("clinical_extension_json", sa.Text(), nullable=True))
    _add_col("strategy_use_events", sa.Column("clinical_extension_json", sa.Text(), nullable=True))


def downgrade() -> None:
    for table in ("session_goal_entries", "strategy_use_events"):
        if has_column(table, "clinical_extension_json"):
            op.drop_column(table, "clinical_extension_json")
