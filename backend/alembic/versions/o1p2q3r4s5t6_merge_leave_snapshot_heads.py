"""Merge leave year snapshots head with therapist approved_snapshot head.

Revision ID: o1p2q3r4s5t6
Revises: n0o1p2q3r4s5, tp_appr_snapshot_2606
Create Date: 2026-06-20

Both migrations branch from m9n0o1p2q3r4; production requires a single Alembic head.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "o1p2q3r4s5t6"
down_revision: Union[str, Sequence[str], None] = (
    "n0o1p2q3r4s5",
    "tp_appr_snapshot_2606",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
