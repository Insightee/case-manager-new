"""Ensure case_documents evidence link columns exist.

Revision ID: u0v1w2x3y4z5
Revises: t3u4v5w6x7y8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "u0v1w2x3y4z5"
down_revision: Union[str, None] = "g1s2t3u4v5w6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("case_documents"):
        return
    for col, coltype in [
        ("linked_report_id", sa.Integer()),
        ("linked_goal_id", sa.Integer()),
        ("linked_strategy_id", sa.Integer()),
        ("domain_key", sa.String(64)),
    ]:
        if not has_column("case_documents", col):
            op.add_column("case_documents", sa.Column(col, coltype, nullable=True))


def downgrade() -> None:
    if not has_table("case_documents"):
        return
    for col in ("linked_report_id", "linked_goal_id", "linked_strategy_id", "domain_key"):
        if has_column("case_documents", col):
            op.drop_column("case_documents", col)
