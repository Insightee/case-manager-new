"""Add academic_qualification_level on therapist_profiles."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tp_qual_level_2703"
down_revision = "s7p0t3m4p5l6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("therapist_profiles")}
    if "academic_qualification_level" not in cols:
        op.add_column(
            "therapist_profiles",
            sa.Column("academic_qualification_level", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("therapist_profiles")}
    if "academic_qualification_level" in cols:
        op.drop_column("therapist_profiles", "academic_qualification_level")
