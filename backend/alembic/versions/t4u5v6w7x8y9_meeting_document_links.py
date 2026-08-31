"""meeting document links

Revision ID: t4u5v6w7x8y9
Revises: s2t3u4v5w6x7
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t4u5v6w7x8y9"
down_revision: Union[str, None] = "s2t3u4v5w6x7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("case_documents", sa.Column("meeting_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("case_documents") as batch:
        batch.create_foreign_key(
            "fk_case_documents_meeting_id",
            "case_manager_meetings",
            ["meeting_id"],
            ["id"],
        )
    op.create_index("ix_case_documents_meeting_id", "case_documents", ["meeting_id"])


def downgrade() -> None:
    op.drop_index("ix_case_documents_meeting_id", table_name="case_documents")
    with op.batch_alter_table("case_documents") as batch:
        batch.drop_constraint("fk_case_documents_meeting_id", type_="foreignkey")
    op.drop_column("case_documents", "meeting_id")
