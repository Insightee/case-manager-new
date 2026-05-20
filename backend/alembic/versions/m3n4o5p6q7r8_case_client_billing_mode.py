"""case client_billing_mode for family invoices

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("cases", "client_billing_mode"):
        with op.batch_alter_table("cases", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "client_billing_mode",
                    sa.Enum("PREPAID", "POSTPAID", name="clientbillingmode"),
                    nullable=True,
                )
            )


def downgrade() -> None:
    if _has_column("cases", "client_billing_mode"):
        with op.batch_alter_table("cases", schema=None) as batch_op:
            batch_op.drop_column("client_billing_mode")
