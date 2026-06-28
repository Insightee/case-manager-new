"""Clinical Brain repository metadata + strategy stats rollup.

Revision ID: d2e3f4a5b6c7
Revises: c1e2x3t4n5j6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1e2x3t4n5j6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_col(table: str, col: sa.Column) -> None:
    if not has_column(table, col.name):
        op.add_column(table, col)


def upgrade() -> None:
    for table in ("goal_repository_items", "strategy_repository_items"):
        _add_col(table, sa.Column("metadata_json", sa.Text(), nullable=True))
        _add_col(table, sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True))

    if not has_table("strategy_repository_stats"):
        op.create_table(
            "strategy_repository_stats",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "strategy_repository_item_id",
                sa.Integer(),
                sa.ForeignKey("strategy_repository_items.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("goal_domain", sa.String(64), nullable=True),
            sa.Column("support_need", sa.String(64), nullable=True),
            sa.Column("environment_context", sa.String(32), nullable=True),
            sa.Column("support_level_tier", sa.String(32), nullable=True),
            sa.Column("total_uses", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("partly_helpful_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("not_helpful_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("child_rejected_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("needs_adaptation_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("adapted_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("evidence_strength", sa.String(32), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "ix_strategy_repository_stats_item_facets",
            "strategy_repository_stats",
            ["strategy_repository_item_id", "goal_domain", "support_need", "environment_context", "support_level_tier"],
            unique=True,
        )


def downgrade() -> None:
    if has_table("strategy_repository_stats"):
        op.drop_table("strategy_repository_stats")
    for table in ("goal_repository_items", "strategy_repository_items"):
        if has_column(table, "last_reviewed_at"):
            op.drop_column(table, "last_reviewed_at")
        if has_column(table, "metadata_json"):
            op.drop_column(table, "metadata_json")
