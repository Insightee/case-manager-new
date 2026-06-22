"""Goals engine v2 — extended repository JSON fields.

Revision ID: u5v6w7x8y9z0
Revises: t3u4v5w6x7y8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column

revision: str = "u5v6w7x8y9z0"
down_revision: Union[str, None] = "u0v1w2x3y4z5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_col(table: str, col: sa.Column) -> None:
    if not has_column(table, col.name):
        op.add_column(table, col)


def upgrade() -> None:
    for col in (
        sa.Column("core_domains_json", sa.Text(), nullable=True),
        sa.Column("core_environments_json", sa.Text(), nullable=True),
        sa.Column("baseline_state", sa.Text(), nullable=True),
        sa.Column("desired_state", sa.Text(), nullable=True),
        sa.Column("goal_statement", sa.Text(), nullable=True),
        sa.Column("lifecycle_status", sa.String(32), nullable=True),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column("scope", sa.String(32), nullable=True),
    ):
        _add_col("goal_repository_items", col)

    for col in (
        sa.Column("core_domains_json", sa.Text(), nullable=True),
        sa.Column("core_environments_json", sa.Text(), nullable=True),
        sa.Column("strategy_steps_json", sa.Text(), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column("scope", sa.String(32), nullable=True),
    ):
        _add_col("strategy_repository_items", col)

    _add_col("strategy_use_events", sa.Column("strategy_steps_json", sa.Text(), nullable=True))
    _add_col("strategy_use_events", sa.Column("expected_outcome", sa.Text(), nullable=True))
    _add_col("strategy_use_events", sa.Column("effectiveness_rating", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    pass
