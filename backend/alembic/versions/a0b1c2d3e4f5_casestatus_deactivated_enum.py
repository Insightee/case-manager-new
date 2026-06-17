"""add DEACTIVATED to casestatus Postgres enum

Revision ID: a0b1c2d3e4f5
Revises: b5c6d7e8f9a0
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_enum_value(enum_name: str, value: str) -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def upgrade() -> None:
    _pg_enum_value("casestatus", "DEACTIVATED")


def downgrade() -> None:
    # Postgres cannot remove enum values safely; no-op.
    pass
