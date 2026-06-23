"""Merge session dispute and pending replacement heads.

Revision ID: d0b7effca6df
Revises: c6b1725843e6, p2q3r4s5t6u7
Create Date: 2026-06-23

Session dispute columns (c6b1725843e6) and PENDING_REPLACEMENT casestatus enum
(p2q3r4s5t6u7) both branch from o1p2q3r4s5t6. Production requires a single
Alembic head; this no-op merge unifies them without rewriting either branch.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d0b7effca6df"
down_revision: Union[str, Sequence[str], None] = (
    "c6b1725843e6",
    "p2q3r4s5t6u7",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
