"""Merge main deploy head with daily_log resubmitted_at branch

Revision ID: c0d1e2f3a4b6
Revises: a0b1c2d3e4f5, a2b3c4d5e6f8
Create Date: 2026-06-19

Production deploy failed because a2b3c4d5e6f8 branched from y8z9a0b1c2d3 while
a0b1c2d3e4f5 remained the main head. migrate_production.py requires a single head.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c0d1e2f3a4b6"
down_revision: Union[str, Sequence[str], None] = ("a0b1c2d3e4f5", "a2b3c4d5e6f8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
