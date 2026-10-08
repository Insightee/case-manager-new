"""Staff attendance work mode and clock-in location."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migration_util import has_table

revision: str = "st4ff4tt3nd2"
down_revision: Union[str, None] = "tvault001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _work_mode_column():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE staffworkmode AS ENUM ('OFFICE', 'WFH');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        return postgresql.ENUM("OFFICE", "WFH", name="staffworkmode", create_type=False)
    return sa.Enum("OFFICE", "WFH", name="staffworkmode")


def upgrade() -> None:
    if not has_table("staff_attendance"):
        return
    work_mode = _work_mode_column()
    with op.batch_alter_table("staff_attendance") as batch_op:
        batch_op.add_column(sa.Column("work_mode", work_mode, nullable=True))
        batch_op.add_column(sa.Column("clock_in_latitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("clock_in_longitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("clock_in_accuracy_meters", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("distance_from_office_meters", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("clock_in_place_label", sa.String(length=512), nullable=True))


def downgrade() -> None:
    if not has_table("staff_attendance"):
        return
    with op.batch_alter_table("staff_attendance") as batch_op:
        batch_op.drop_column("clock_in_place_label")
        batch_op.drop_column("distance_from_office_meters")
        batch_op.drop_column("clock_in_accuracy_meters")
        batch_op.drop_column("clock_in_longitude")
        batch_op.drop_column("clock_in_latitude")
        batch_op.drop_column("work_mode")
