"""ticket_messages is_internal

Revision ID: y9z0a1b2c3d4
Revises: x8y9z0a1b2c3
Create Date: 2026-05-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y9z0a1b2c3d4"
down_revision: Union[str, None] = "x8y9z0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("ticket_messages"):
        cols = {c["name"] for c in insp.get_columns("ticket_messages")}
        if "is_internal" not in cols:
            op.add_column(
                "ticket_messages",
                sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.false()),
            )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("ticket_messages"):
        cols = {c["name"] for c in insp.get_columns("ticket_messages")}
        if "is_internal" in cols:
            op.drop_column("ticket_messages", "is_internal")
