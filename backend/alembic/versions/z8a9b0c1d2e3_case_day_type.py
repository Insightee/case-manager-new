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
    if _has_column("cases", "day_type"):
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE casedaytype AS ENUM ('HALF_DAY', 'FULL_DAY');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        day_type_col = sa.Enum("HALF_DAY", "FULL_DAY", name="casedaytype", create_type=False)
        op.add_column("cases", sa.Column("day_type", day_type_col, nullable=True))
        op.create_index("ix_cases_day_type", "cases", ["day_type"], unique=False)
    else:
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
    if not _has_column("cases", "day_type"):
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("ix_cases_day_type", table_name="cases")
        op.drop_column("cases", "day_type")
        bind.execute(sa.text("DROP TYPE IF EXISTS casedaytype"))
    else:
        with op.batch_alter_table("cases", schema=None) as batch_op:
            batch_op.drop_index("ix_cases_day_type")
            batch_op.drop_column("day_type")
