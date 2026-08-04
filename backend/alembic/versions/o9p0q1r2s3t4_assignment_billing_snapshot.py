"""case_assignments billing_snapshot for locked outgoing therapist billing

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "o9p0q1r2s3t4"
down_revision: Union[str, None] = "n8o9p0q1r2s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("case_assignments"):
        return
    cols = {c["name"] for c in insp.get_columns("case_assignments")}
    if "billing_snapshot" not in cols:
        with op.batch_alter_table("case_assignments", schema=None) as batch_op:
            batch_op.add_column(sa.Column("billing_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("case_assignments"):
        return
    cols = {c["name"] for c in insp.get_columns("case_assignments")}
    if "billing_snapshot" in cols:
        with op.batch_alter_table("case_assignments", schema=None) as batch_op:
            batch_op.drop_column("billing_snapshot")
