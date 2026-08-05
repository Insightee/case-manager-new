"""Merge ticket department queue and dispute grievance heads

Revision ID: h4i5j6k7l8m9
Revises: f3a4b5c6d7e9, g2b3c4d5e6f9
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op

revision: str = "h4i5j6k7l8m9"
down_revision: Union[str, Sequence[str], None] = (
    "f3a4b5c6d7e9",
    "g2b3c4d5e6f9",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
