"""therapist profile soft delete (DELETED status + deleted_at)

Revision ID: a8b9c0d1e2f3
Revises: a1b2c3d4e5f8
Create Date: 2026-08-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "a1b2c3d4e5f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_enum_value(enum_name: str, value: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def upgrade() -> None:
    _pg_enum_value("therapistprofilestatus", "DELETED")
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("therapist_profiles"):
        cols = {c["name"] for c in insp.get_columns("therapist_profiles")}
        if "deleted_at" not in cols:
            op.add_column(
                "therapist_profiles",
                sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("therapist_profiles"):
        cols = {c["name"] for c in insp.get_columns("therapist_profiles")}
        if "deleted_at" in cols:
            op.drop_column("therapist_profiles", "deleted_at")
    # Postgres enum values cannot be removed safely.
