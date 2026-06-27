"""Merge comment lifecycle head with meeting enum expansion branch.

Revision ID: p0q1r2s3t4u5
Revises: 71f1c9848214, a1b2c3d4e5f8
Create Date: 2026-06-27

Production deploy failed because 71f1c9848214 and z9c0d1e2f3a7 -> a1b2c3d4e5f8
both branched from d0b7effca6df. migrate_production.py requires a single head.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "p0q1r2s3t4u5"
down_revision: Union[str, Sequence[str], None] = ("71f1c9848214", "a1b2c3d4e5f8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
