"""Add product_modules JSON to service_categories

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-05-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r0s1t2u3v4w5"
down_revision: Union[str, None] = "q9r0s1t2u3v4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("service_categories", sa.Column("product_modules", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("service_categories", "product_modules")
