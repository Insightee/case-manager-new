"""Add secondary contact fields on users for parent portal."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("secondary_contact_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("secondary_contact_email", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "secondary_contact_email")
    op.drop_column("users", "secondary_contact_name")
