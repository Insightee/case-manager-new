"""parent reports hub — comments and parent review on monthly reports

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=False),
        sa.Column("comment_type", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_comments_entity", "document_comments", ["entity_type", "entity_id"])
    op.create_index("ix_document_comments_case_id", "document_comments", ["case_id"])

    with op.batch_alter_table("monthly_reports", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_review_status", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("parent_feedback", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("parent_reviewed_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        "UPDATE monthly_reports SET parent_review_status = 'APPROVED' "
        "WHERE status = 'PUBLISHED' AND visibility_status IN ('APPROVED_FOR_PARENT', 'SHARED_WITH_PARENT')"
    )


def downgrade() -> None:
    with op.batch_alter_table("monthly_reports", schema=None) as batch_op:
        batch_op.drop_column("parent_reviewed_at")
        batch_op.drop_column("parent_feedback")
        batch_op.drop_column("parent_review_status")
    op.drop_index("ix_document_comments_case_id", table_name="document_comments")
    op.drop_index("ix_document_comments_entity", table_name="document_comments")
    op.drop_table("document_comments")
