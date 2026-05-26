"""incident tagged_user_ids

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q9r0s1t2u3v4"
down_revision: Union[str, None] = "p8q9r0s1t2u3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("tagged_user_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("incidents", "tagged_user_ids")
