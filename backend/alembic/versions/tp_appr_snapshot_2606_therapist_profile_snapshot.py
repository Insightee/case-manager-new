"""Add approved_snapshot to therapist_profiles for review diffs.

Revision ID: tp_appr_snapshot_2606
Revises: m9n0o1p2q3r4
Create Date: 2026-06-20

Stores the therapist-editable fields as of the last admin approval so the
review screen can show a before/after diff of pending edits without a separate
change-request table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tp_appr_snapshot_2606"
down_revision = "m9n0o1p2q3r4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("therapist_profiles")} if insp.has_table("therapist_profiles") else set()
    if "approved_snapshot" not in cols:
        op.add_column("therapist_profiles", sa.Column("approved_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("therapist_profiles", "approved_snapshot")
