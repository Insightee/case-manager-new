"""Grant every case on an integration client without listing each id.

Revision ID: i2all3cases4fin
Revises: tp_qual_cards_1001
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "i2all3cases4fin"
down_revision: Union[str, None] = "tp_qual_cards_1001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("integration_clients"):
        return
    if has_column("integration_clients", "all_cases"):
        return
    with op.batch_alter_table("integration_clients") as batch:
        batch.add_column(sa.Column("all_cases", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    if not has_table("integration_clients"):
        return
    if not has_column("integration_clients", "all_cases"):
        return
    with op.batch_alter_table("integration_clients") as batch:
        batch.drop_column("all_cases")
