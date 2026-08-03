"""Add therapist-scoped meeting notes column

Revision ID: m7n8o9p0q1r2
Revises: c2d3e4f5a6b7
Create Date: 2026-08-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m7n8o9p0q1r2"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("case_manager_meetings", sa.Column("therapist_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("case_manager_meetings", "therapist_notes")
