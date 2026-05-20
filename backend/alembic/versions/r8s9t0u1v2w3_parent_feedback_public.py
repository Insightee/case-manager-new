"""parent session feedback public flag

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column

revision: str = "r8s9t0u1v2w3"
down_revision: Union[str, None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("daily_logs", "parent_feedback_public"):
        with op.batch_alter_table("daily_logs") as batch_op:
            batch_op.add_column(
                sa.Column("parent_feedback_public", sa.Boolean(), nullable=False, server_default=sa.false())
            )


def downgrade() -> None:
    if has_column("daily_logs", "parent_feedback_public"):
        with op.batch_alter_table("daily_logs") as batch_op:
            batch_op.drop_column("parent_feedback_public")
