"""add TECH support ticket category

Revision ID: tk3c4d5e6f7
Revises: tr2b3c4d5e6
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = "tk3c4d5e6f7"
down_revision: Union[str, None] = "tr2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("ALTER TYPE ticketcategory ADD VALUE IF NOT EXISTS 'TECH'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely.
    pass
