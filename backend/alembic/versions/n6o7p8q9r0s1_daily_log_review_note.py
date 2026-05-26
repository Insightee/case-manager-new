"""daily_logs review_note for reject comments

Revision ID: n6o7p8q9r0s1
Revises: m8n9o0p1q2r3
Create Date: 2026-05-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n6o7p8q9r0s1"
down_revision: Union[str, None] = "m8n9o0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("daily_logs", sa.Column("review_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("daily_logs", "review_note")
