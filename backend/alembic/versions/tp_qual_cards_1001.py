"""Qualification cards JSON + CHANGES_REQUESTED listing status."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tp_qual_cards_1001"
down_revision = "tp_qual_level_2703"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("therapist_profiles")}
    if "professional_qualification_entries" not in cols:
        op.add_column(
            "therapist_profiles",
            sa.Column("professional_qualification_entries", sa.JSON(), nullable=True),
        )
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE therapistprofilestatus ADD VALUE IF NOT EXISTS 'CHANGES_REQUESTED'")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("therapist_profiles")}
    if "professional_qualification_entries" in cols:
        op.drop_column("therapist_profiles", "professional_qualification_entries")
