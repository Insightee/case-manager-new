"""Case documents P1: case_documents, versions, workflow events.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_table

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = ("c4d5e6f7a8b9", "d4e5f6a7b8c9")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("case_documents"):
        return

    op.create_table(
        "case_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(48), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("report_month", sa.String(32), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("visibility", sa.String(48), nullable=False, server_default="INTERNAL_ONLY"),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("parent_review_status", sa.String(32), nullable=True),
        sa.Column("parent_feedback", sa.Text(), nullable=True),
        sa.Column("parent_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("legacy_entity_type", sa.String(32), nullable=True),
        sa.Column("legacy_entity_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
    )

    op.create_table(
        "case_document_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_document_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("external_provider", sa.String(32), nullable=True),
        sa.Column("external_url", sa.String(2048), nullable=True),
        sa.Column("external_file_id", sa.String(128), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_document_id"], ["case_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("case_document_id", "version_number", name="uq_case_document_version"),
    )

    with op.batch_alter_table("case_documents") as batch:
        batch.create_foreign_key(
            "fk_case_documents_current_version",
            "case_document_versions",
            ["current_version_id"],
            ["id"],
        )

    op.create_table(
        "case_document_workflow_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_document_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["case_document_id"], ["case_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
    )

    create_index_if_missing("ix_case_documents_case_status", "case_documents", ["case_id", "status"])
    create_index_if_missing("ix_case_documents_case_category", "case_documents", ["case_id", "category"])
    create_index_if_missing("ix_case_documents_submitted_by", "case_documents", ["submitted_by_user_id"])
    create_index_if_missing("ix_case_documents_case_visibility", "case_documents", ["case_id", "visibility"])


def downgrade() -> None:
    if not has_table("case_documents"):
        return
    op.drop_table("case_document_workflow_events")
    op.drop_table("case_document_versions")
    op.drop_table("case_documents")
