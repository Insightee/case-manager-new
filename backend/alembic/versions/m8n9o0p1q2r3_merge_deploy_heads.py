"""Merge deploy heads (is_view_only, rbac/documents, service_categories)

Revision ID: m8n9o0p1q2r3
Revises: c7d8e9f0a1b2, d7e8f9a0b1c2, b2c3d4e5f6g7
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op

revision: str = "m8n9o0p1q2r3"
down_revision: Union[str, Sequence[str], None] = (
    "c7d8e9f0a1b2",
    "d7e8f9a0b1c2",
    "b2c3d4e5f6g7",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
