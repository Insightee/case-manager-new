"""incident shared_with_family flag

Revision ID: inc8share20261008
Revises: pmr7req20261005
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "inc8share20261008"
down_revision: Union[str, None] = "pmr7req20261005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("shared_with_family", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("incidents", "shared_with_family")
