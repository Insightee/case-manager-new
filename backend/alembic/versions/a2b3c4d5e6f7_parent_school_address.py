"""parent school address columns on users

Revision ID: a2b3c4d5e6f7
Revises: w9x0y1z2a3b4
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "w9x0y1z2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHOOL_COLS = [
    ("school_address_line1", sa.String(255)),
    ("school_address_line2", sa.String(255)),
    ("school_city", sa.String(128)),
    ("school_state", sa.String(128)),
    ("school_pincode", sa.String(16)),
    ("school_landmark", sa.String(255)),
    ("school_latitude", sa.Float()),
    ("school_longitude", sa.Float()),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    user_cols = {c["name"] for c in insp.get_columns("users")}

    with op.batch_alter_table("users") as batch_op:
        for name, col_type in _SCHOOL_COLS:
            if name not in user_cols:
                batch_op.add_column(sa.Column(name, col_type, nullable=True))
        if "preferred_visit_address_type" not in user_cols:
            batch_op.add_column(
                sa.Column("preferred_visit_address_type", sa.String(length=16), nullable=True, server_default="home")
            )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("preferred_visit_address_type")
        for name, _ in reversed(_SCHOOL_COLS):
            batch_op.drop_column(name)
