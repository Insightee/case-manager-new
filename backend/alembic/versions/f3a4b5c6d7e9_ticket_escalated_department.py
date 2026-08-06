"""support_tickets escalated_to_department queue

Revision ID: f3a4b5c6d7e9
Revises: f2a3b4c5d6e8
Create Date: 2026-08-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a4b5c6d7e9"
down_revision: Union[str, None] = "g2b3c4d5e6f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("support_tickets"):
        cols = {c["name"] for c in insp.get_columns("support_tickets")}
        if "escalated_to_department" not in cols:
            op.add_column(
                "support_tickets",
                sa.Column("escalated_to_department", sa.String(length=64), nullable=True),
            )
            op.create_index(
                "ix_support_tickets_escalated_to_department",
                "support_tickets",
                ["escalated_to_department"],
                unique=False,
            )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("support_tickets"):
        cols = {c["name"] for c in insp.get_columns("support_tickets")}
        if "escalated_to_department" in cols:
            op.drop_index("ix_support_tickets_escalated_to_department", table_name="support_tickets")
            op.drop_column("support_tickets", "escalated_to_department")
