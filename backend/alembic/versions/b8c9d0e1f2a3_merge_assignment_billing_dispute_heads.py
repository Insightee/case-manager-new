"""Merge assignment billing snapshot and therapist statement disputes heads.

Revision ID: b8c9d0e1f2a3
Revises: a7d9f2c4e6b8, o9p0q1r2s3t4
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = (
    "a7d9f2c4e6b8",
    "o9p0q1r2s3t4",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
