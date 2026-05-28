"""Add staff_attendee_user_ids_json to case_manager_meetings.

Revision ID: z9a0b1c2d3e4
Revises: y8z9a0b1c2d3
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z9a0b1c2d3e4"
down_revision: Union[str, None] = "y8z9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_manager_meetings",
        sa.Column("staff_attendee_user_ids_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("case_manager_meetings", "staff_attendee_user_ids_json")
