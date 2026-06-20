"""Add leave_year_snapshots JSON on therapist_profiles for bulk import overrides."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "n0o1p2q3r4s5"
down_revision = "m9n0o1p2q3r4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("therapist_profiles", sa.Column("leave_year_snapshots", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("therapist_profiles", "leave_year_snapshots")
