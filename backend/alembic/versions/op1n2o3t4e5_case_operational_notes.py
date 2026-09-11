"""Case operational notes journal (staff-only, append-only).

Revision ID: op1n2o3t4e5
Revises: v6w7x8y9z0a1
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "op1n2o3t4e5"
down_revision: Union[str, None] = "v6w7x8y9z0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("case_operational_notes"):
        op.create_table(
            "case_operational_notes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("heading", sa.String(length=200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("author_user_id", sa.Integer(), nullable=True),
            sa.Column("is_legacy_import", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_case_operational_notes_case_id", "case_operational_notes", ["case_id"])

    if has_table("cases") and has_table("case_operational_notes"):
        conn = op.get_bind()
        conn.execute(
            sa.text(
                """
                INSERT INTO case_operational_notes (case_id, heading, body, author_user_id, is_legacy_import)
                SELECT c.id, 'Legacy note', c.notes, NULL, TRUE
                FROM cases c
                WHERE c.notes IS NOT NULL
                  AND TRIM(c.notes) != ''
                  AND NOT EXISTS (
                    SELECT 1 FROM case_operational_notes n WHERE n.case_id = c.id
                  )
                """
            )
        )


def downgrade() -> None:
    if has_table("case_operational_notes"):
        op.drop_index("ix_case_operational_notes_case_id", table_name="case_operational_notes")
        op.drop_table("case_operational_notes")
