"""Add structured_session_json to daily_logs.

Revision ID: w1x2y3z4a5b6
Revises: v0i1c2e3a4b5
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "w1x2y3z4a5b6"
down_revision: Union[str, None] = "v0i1c2e3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("daily_logs") and not has_column("daily_logs", "structured_session_json"):
        op.add_column("daily_logs", sa.Column("structured_session_json", sa.Text(), nullable=True))
    if has_table("daily_logs") and not has_column("daily_logs", "therapist_reflection"):
        op.add_column("daily_logs", sa.Column("therapist_reflection", sa.Text(), nullable=True))


def downgrade() -> None:
    if has_table("daily_logs") and has_column("daily_logs", "therapist_reflection"):
        op.drop_column("daily_logs", "therapist_reflection")
    if has_table("daily_logs") and has_column("daily_logs", "structured_session_json"):
        op.drop_column("daily_logs", "structured_session_json")
