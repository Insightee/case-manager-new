"""Case insight actions — staged insight selections for monthly report / IEP review.

Revision ID: i2n5s8g7h4t9
Revises: 34b3b615ccae
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "i2n5s8g7h4t9"
down_revision: Union[str, None] = "34b3b615ccae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("case_insight_actions"):
        return
    op.create_table(
        "case_insight_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("insight_id", sa.String(128), nullable=False),
        sa.Column("insight_snapshot_json", sa.Text(), nullable=False),
        sa.Column("destination", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_review"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_case_insight_actions_case_id", "case_insight_actions", ["case_id"])
    op.create_index("ix_case_insight_actions_insight_id", "case_insight_actions", ["insight_id"])
    op.create_index("ix_case_insight_actions_destination", "case_insight_actions", ["destination"])
    op.create_index("ix_case_insight_actions_status", "case_insight_actions", ["status"])


def downgrade() -> None:
    op.drop_table("case_insight_actions")
