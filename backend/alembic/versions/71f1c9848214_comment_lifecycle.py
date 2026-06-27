"""comment_lifecycle

Revision ID: 71f1c9848214
Revises: e2bbb025e3f5
Create Date: 2026-06-23 18:41:20.055029

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '71f1c9848214'
down_revision: Union[str, None] = 'd0b7effca6df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("document_comments"):
        cols = {c["name"] for c in insp.get_columns("document_comments")}
        if "author_role" not in cols:
            op.add_column("document_comments", sa.Column("author_role", sa.String(32), nullable=True))
        if "visibility" not in cols:
            op.add_column("document_comments", sa.Column("visibility", sa.String(32), nullable=False, server_default="parent_team"))
        if "status" not in cols:
            op.add_column("document_comments", sa.Column("status", sa.String(32), nullable=False, server_default="open"))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("document_comments"):
        cols = {c["name"] for c in insp.get_columns("document_comments")}
        if "author_role" in cols:
            op.drop_column("document_comments", "author_role")
        if "visibility" in cols:
            op.drop_column("document_comments", "visibility")
        if "status" in cols:
            op.drop_column("document_comments", "status")
