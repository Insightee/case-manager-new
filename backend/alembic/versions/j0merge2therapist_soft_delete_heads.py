"""Merge therapist profile soft-delete head with integration API head.

Revision ID: j0merge2therapist
Revises: a8b9c0d1e2f3, i1integr2api3layer
Create Date: 2026-08-28

Greenfield test bootstrap and migrate_production.py require a single Alembic head.
"""
from typing import Sequence, Union

revision: str = "j0merge2therapist"
down_revision: Union[str, Sequence[str], None] = ("a8b9c0d1e2f3", "i1integr2api3layer")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
