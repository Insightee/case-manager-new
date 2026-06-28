"""Phase 2 — iep_review_suggestions table.

Revision ID: s2t3u4v5w6x7
Revises: r1s2t3u4v5w6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "s2t3u4v5w6x7"
down_revision: Union[str, None] = "r1s2t3u4v5w6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("iep_review_suggestions"):
        op.create_table(
            "iep_review_suggestions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False, index=True),
            sa.Column("iep_plan_id", sa.Integer(), sa.ForeignKey("iep_plans.id"), nullable=True, index=True),
            sa.Column("goal_card_id", sa.Integer(), sa.ForeignKey("iep_goal_cards.id"), nullable=True),
            sa.Column("strategy_id", sa.Integer(), sa.ForeignKey("strategy_repository_items.id"), nullable=True),
            sa.Column("suggestion_type", sa.String(64), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("supporting_evidence_json", sa.Text(), nullable=True),
            sa.Column("confidence", sa.String(16), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft", index=True),
            sa.Column("dismissed_reason", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    if has_table("iep_review_suggestions"):
        op.drop_table("iep_review_suggestions")
