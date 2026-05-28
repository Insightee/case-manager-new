"""Add editable staff profile fields on users.

Revision ID: p1q2r3s4t5u6
Revises: z9a0b1c2d3e4
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, None] = "z9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.String(length=2000), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("timezone", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("ui_preferences", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("notification_preferences", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "notification_preferences")
    op.drop_column("users", "ui_preferences")
    op.drop_column("users", "timezone")
    op.drop_column("users", "department")
    op.drop_column("users", "job_title")
    op.drop_column("users", "bio")
