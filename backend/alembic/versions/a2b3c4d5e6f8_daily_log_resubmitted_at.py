"""daily_logs resubmitted_at for queue ordering and admin review context

Revision ID: a2b3c4d5e6f8
Revises: y8z9a0b1c2d3
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column

revision: str = "a2b3c4d5e6f8"
down_revision: Union[str, None] = "y8z9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("daily_logs", "resubmitted_at"):
        op.add_column(
            "daily_logs",
            sa.Column("resubmitted_at", sa.DateTime(timezone=True), nullable=True),
        )
    bind = op.get_bind()
    insp = sa.inspect(bind)
    index_names = {idx["name"] for idx in insp.get_indexes("daily_logs")}
    if "ix_daily_logs_resubmitted_at" not in index_names:
        op.create_index("ix_daily_logs_resubmitted_at", "daily_logs", ["resubmitted_at"])


def downgrade() -> None:
    op.drop_index("ix_daily_logs_resubmitted_at", table_name="daily_logs")
    op.drop_column("daily_logs", "resubmitted_at")
