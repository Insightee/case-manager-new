"""Identity registry + session evidence taps (empty tables; no backfill).

Revision ID: s4e5v6i7d8e9
Revises: ba5p6p7r8v9
Create Date: 2026-08-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s4e5v6i7d8e9"
down_revision: Union[str, None] = "ba5p6p7r8v9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "iep_goal_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("iep_plan_id", sa.Integer(), nullable=False),
        sa.Column("statement", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["iep_plan_id"], ["iep_plans.id"]),
        sa.UniqueConstraint("iep_plan_id", "statement", name="uq_iep_goal_items_plan_statement"),
    )
    op.create_index("ix_iep_goal_items_iep_plan_id", "iep_goal_items", ["iep_plan_id"])

    op.create_table(
        "iep_strategy_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("iep_plan_id", sa.Integer(), nullable=False),
        sa.Column("statement", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["iep_plan_id"], ["iep_plans.id"]),
        sa.UniqueConstraint("iep_plan_id", "statement", name="uq_iep_strategy_items_plan_statement"),
    )
    op.create_index("ix_iep_strategy_items_iep_plan_id", "iep_strategy_items", ["iep_plan_id"])

    op.create_table(
        "session_goal_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_log_id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("participation", sa.String(32), nullable=False),
        sa.Column("support_level", sa.String(32), nullable=False),
        sa.Column("achievement", sa.String(32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["daily_log_id"], ["daily_logs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_id"], ["iep_goal_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_session_goal_entries_daily_log_id", "session_goal_entries", ["daily_log_id"])

    op.create_table(
        "strategy_use_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_log_id", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("response", sa.String(32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["daily_log_id"], ["daily_logs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["iep_strategy_items.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_strategy_use_events_daily_log_id", "strategy_use_events", ["daily_log_id"])


def downgrade() -> None:
    op.drop_index("ix_strategy_use_events_daily_log_id", table_name="strategy_use_events")
    op.drop_table("strategy_use_events")
    op.drop_index("ix_session_goal_entries_daily_log_id", table_name="session_goal_entries")
    op.drop_table("session_goal_entries")
    op.drop_index("ix_iep_strategy_items_iep_plan_id", table_name="iep_strategy_items")
    op.drop_table("iep_strategy_items")
    op.drop_index("ix_iep_goal_items_iep_plan_id", table_name="iep_goal_items")
    op.drop_table("iep_goal_items")
