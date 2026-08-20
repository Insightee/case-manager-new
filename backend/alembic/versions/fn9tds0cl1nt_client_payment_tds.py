"""Optional TDS withheld by the payer on client payments.

Revision ID: fn9tds0cl1nt
Revises: d8r9e0p1o2r3
Create Date: 2026-08-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "fn9tds0cl1nt"
down_revision: Union[str, None] = "d8r9e0p1o2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _has_column("client_payments", "tds_inr"):
        op.add_column(
            "client_payments",
            sa.Column("tds_inr", sa.Numeric(12, 2), nullable=True, server_default="0"),
        )


def downgrade() -> None:
    if _has_column("client_payments", "tds_inr"):
        op.drop_column("client_payments", "tds_inr")
