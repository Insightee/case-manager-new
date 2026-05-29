"""case assignment acceptance timestamps

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = [
    ("therapist_accepted_at", sa.DateTime(timezone=True)),
    ("parent_accepted_at", sa.DateTime(timezone=True)),
    ("assignment_offer_sent_at", sa.DateTime(timezone=True)),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("case_assignments"):
        return
    existing = {c["name"] for c in insp.get_columns("case_assignments")}
    for name, col_type in _COLS:
        if name not in existing:
            op.add_column("case_assignments", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("case_assignments"):
        return
    existing = {c["name"] for c in insp.get_columns("case_assignments")}
    for name, _ in reversed(_COLS):
        if name in existing:
            op.drop_column("case_assignments", name)
