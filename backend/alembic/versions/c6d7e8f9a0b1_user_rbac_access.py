"""Add RBAC grant columns on users

Revision ID: c6d7e8f9a0b1
Revises: k3l4m5n6o7p8
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column

revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "k3l4m5n6o7p8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("users", "module_access_grants"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("module_access_grants", sa.JSON(), nullable=True))
    if not has_column("users", "feature_overrides"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("feature_overrides", sa.JSON(), nullable=True))


def downgrade() -> None:
    if has_column("users", "feature_overrides"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("feature_overrides")
    if has_column("users", "module_access_grants"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("module_access_grants")
