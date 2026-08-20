"""Add cases.zoho_id for client billing identifiers.

Revision ID: z1o2h3o4i5d6
Revises: d8r9e0p1o2r3
Create Date: 2026-08-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_column

revision: str = "z1o2h3o4i5d6"
down_revision: Union[str, None] = "d8r9e0p1o2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("cases", "zoho_id"):
        op.add_column("cases", sa.Column("zoho_id", sa.String(length=64), nullable=True))
    create_index_if_missing("ix_cases_zoho_id", "cases", ["zoho_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("cases"):
        indexes = {idx["name"] for idx in insp.get_indexes("cases")}
        if "ix_cases_zoho_id" in indexes:
            op.drop_index("ix_cases_zoho_id", table_name="cases")
        if has_column("cases", "zoho_id"):
            op.drop_column("cases", "zoho_id")
