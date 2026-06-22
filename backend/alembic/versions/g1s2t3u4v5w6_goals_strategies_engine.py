"""Goals & strategies engine — scoring columns and review audit.

Revision ID: g1s2t3u4v5w6
Revises: t3u4v5w6x7y8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_column, has_table

revision: str = "g1s2t3u4v5w6"
down_revision: Union[str, None] = "t3u4v5w6x7y8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_col(table: str, col: sa.Column) -> None:
    if not has_column(table, col.name):
        op.add_column(table, col)


def upgrade() -> None:
    _add_col("session_goal_entries", sa.Column("session_id", sa.Integer(), nullable=True))
    _add_col("session_goal_entries", sa.Column("case_id", sa.Integer(), nullable=True))
    _add_col("session_goal_entries", sa.Column("child_id", sa.Integer(), nullable=True))
    _add_col("session_goal_entries", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    _add_col("session_goal_entries", sa.Column("participation_score", sa.SmallInteger(), nullable=True))
    _add_col("session_goal_entries", sa.Column("independence_score", sa.SmallInteger(), nullable=True))
    _add_col("session_goal_entries", sa.Column("goal_achievement_score", sa.SmallInteger(), nullable=True))
    _add_col("session_goal_entries", sa.Column("activity_used", sa.Text(), nullable=True))
    _add_col("session_goal_entries", sa.Column("measurement_note", sa.Text(), nullable=True))
    _add_col("session_goal_entries", sa.Column("goal_repository_item_id", sa.Integer(), nullable=True))
    _add_col("session_goal_entries", sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False))
    create_index_if_missing("ix_session_goal_entries_case_id", "session_goal_entries", ["case_id"])
    create_index_if_missing("ix_session_goal_entries_goal_card_id", "session_goal_entries", ["goal_card_id"])

    _add_col("strategy_use_events", sa.Column("session_id", sa.Integer(), nullable=True))
    _add_col("strategy_use_events", sa.Column("case_id", sa.Integer(), nullable=True))
    _add_col("strategy_use_events", sa.Column("child_id", sa.Integer(), nullable=True))
    _add_col("strategy_use_events", sa.Column("goal_card_id", sa.Integer(), nullable=True))
    _add_col("strategy_use_events", sa.Column("goal_entry_id", sa.Integer(), nullable=True))
    _add_col("strategy_use_events", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    _add_col("strategy_use_events", sa.Column("environment", sa.String(32), nullable=True))
    _add_col("strategy_use_events", sa.Column("activity_used", sa.Text(), nullable=True))
    _add_col("strategy_use_events", sa.Column("participation_score", sa.SmallInteger(), nullable=True))
    _add_col("strategy_use_events", sa.Column("independence_score", sa.SmallInteger(), nullable=True))
    _add_col("strategy_use_events", sa.Column("goal_achievement_score", sa.SmallInteger(), nullable=True))
    _add_col("strategy_use_events", sa.Column("strategy_feedback", sa.String(32), nullable=True))
    _add_col("strategy_use_events", sa.Column("short_note", sa.Text(), nullable=True))
    _add_col("strategy_use_events", sa.Column("custom_strategy_id", sa.Integer(), nullable=True))
    create_index_if_missing("ix_strategy_use_events_case_id", "strategy_use_events", ["case_id"])

    _add_col("strategy_repository_items", sa.Column("domain_key", sa.String(64), nullable=True))
    _add_col("strategy_repository_items", sa.Column("environment_context", sa.String(32), nullable=True))
    _add_col("strategy_repository_items", sa.Column("linked_goal_card_id", sa.Integer(), nullable=True))
    _add_col("strategy_repository_items", sa.Column("source_daily_log_id", sa.Integer(), nullable=True))
    _add_col("strategy_repository_items", sa.Column("review_note", sa.Text(), nullable=True))

    _add_col("goal_repository_items", sa.Column("source_daily_log_id", sa.Integer(), nullable=True))
    _add_col("goal_repository_items", sa.Column("source_session_id", sa.Integer(), nullable=True))
    _add_col("goal_repository_items", sa.Column("review_note", sa.Text(), nullable=True))

    _add_col("daily_logs", sa.Column("parent_voice_attachment_id", sa.Integer(), nullable=True))

    if not has_table("repository_review_events"):
        op.create_table(
            "repository_review_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("item_type", sa.String(16), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("merged_into_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_repository_review_events_item", "repository_review_events", ["item_type", "item_id"])


def downgrade() -> None:
    if has_table("repository_review_events"):
        op.drop_table("repository_review_events")
