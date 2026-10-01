"""document privacy defaults

Revision ID: r1s2t3u4v5w6
Revises: q1q2r3s4t5u6
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r1s2t3u4v5w6"
down_revision: Union[str, None] = "q1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "document_comments",
        "visibility",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default="internal_only",
    )


def downgrade() -> None:
    op.alter_column(
        "document_comments",
        "visibility",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default="parent_team",
    )
