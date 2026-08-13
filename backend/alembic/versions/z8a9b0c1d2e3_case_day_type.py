"""case day_type for shadow and b2b

Revision ID: z8a9b0c1d2e3
Revises: h4i5j6k7l8m9
Create Date: 2026-08-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z8a9b0c1d2e3"
down_revision: Union[str, None] = "h4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("cases", "day_type"):
        with op.batch_alter_table("cases", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "day_type",
                    sa.Enum("HALF_DAY", "FULL_DAY", name="casedaytype"),
                    nullable=True,
                )
            )
            batch_op.create_index("ix_cases_day_type", ["day_type"], unique=False)


def downgrade() -> None:
    if _has_column("cases", "day_type"):
        with op.batch_alter_table("cases", schema=None) as batch_op:
            batch_op.drop_index("ix_cases_day_type")
            batch_op.drop_column("day_type")
