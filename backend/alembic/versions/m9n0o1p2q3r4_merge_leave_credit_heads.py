"""Merge leave credit policy v2 head with the deploy merge head.

Revision ID: m9n0o1p2q3r4
Revises: c0d1e2f3a4b6, z0a1b2c3d4e6
Create Date: 2026-06-20

The leave credit policy migration (z0a1b2c3d4e6) branches from y8z9a0b1c2d3,
while c0d1e2f3a4b6 is the main deploy merge head. Production stamped both as
separate heads, so a dedicated merge revision is required to unify them into a
single head without rewriting either branch's history.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "m9n0o1p2q3r4"
down_revision: Union[str, Sequence[str], None] = (
    "c0d1e2f3a4b6",
    "z0a1b2c3d4e6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
