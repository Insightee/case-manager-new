"""add PENDING_REPLACEMENT to casestatus Postgres enum

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "p2q3r4s5t6u7"
down_revision: Union[str, None] = "o1p2q3r4s5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_enum_value(enum_name: str, value: str) -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def upgrade() -> None:
    _pg_enum_value("casestatus", "PENDING_REPLACEMENT")


def downgrade() -> None:
    # Postgres cannot remove enum values safely; no-op.
    pass
