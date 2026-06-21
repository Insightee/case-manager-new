"""Phase 3+ — clinical snapshots, reference docs, retrieval logs.

Revision ID: t3u4v5w6x7y8
Revises: s2t3u4v5w6x7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "t3u4v5w6x7y8"
down_revision: Union[str, None] = "s2t3u4v5w6x7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("clinical_snapshots"):
        op.create_table(
            "clinical_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False, index=True),
            sa.Column("month", sa.String(7), nullable=False, index=True),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("generated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("generated_for_role", sa.String(32), nullable=False, server_default="therapist"),
            sa.Column("insight_type", sa.String(64), nullable=False, index=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft", index=True),
            sa.Column("deterministic_summary_json", sa.Text(), nullable=True),
            sa.Column("ai_output_json", sa.Text(), nullable=True),
            sa.Column("ai_output_text", sa.Text(), nullable=True),
            sa.Column("source_record_ids_json", sa.Text(), nullable=True),
            sa.Column("reference_chunk_ids_json", sa.Text(), nullable=True),
            sa.Column("prompt_version", sa.String(16), nullable=True),
            sa.Column("provider", sa.String(32), server_default="mock"),
            sa.Column("model", sa.String(64), nullable=True),
            sa.Column("input_hash", sa.String(64), nullable=False, index=True),
            sa.Column("output_hash", sa.String(64), nullable=True),
            sa.Column("token_input_count", sa.Integer(), nullable=True),
            sa.Column("token_output_count", sa.Integer(), nullable=True),
            sa.Column("estimated_cost", sa.Float(), nullable=True),
            sa.Column("generation_log_id", sa.Integer(), sa.ForeignKey("ai_generation_logs.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("clinical_snapshot_feedback"):
        op.create_table(
            "clinical_snapshot_feedback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("clinical_snapshots.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("feedback_type", sa.String(32), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("clinical_reference_documents"):
        op.create_table(
            "clinical_reference_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(256), nullable=False),
            sa.Column("document_type", sa.String(64), nullable=False, index=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("source_file_url", sa.String(512), nullable=True),
            sa.Column("version", sa.String(32), server_default="1"),
            sa.Column("status", sa.String(32), server_default="draft", index=True),
            sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("clinical_reference_chunks"):
        op.create_table(
            "clinical_reference_chunks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("clinical_reference_documents.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("chunk_title", sa.String(256), nullable=True),
            sa.Column("chunk_text", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("token_estimate", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("clinical_reference_embeddings"):
        op.create_table(
            "clinical_reference_embeddings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("clinical_reference_chunks.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("embedding_provider", sa.String(32), server_default="none"),
            sa.Column("embedding_model", sa.String(64), nullable=True),
            sa.Column("embedding_vector", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("ai_retrieval_logs"):
        op.create_table(
            "ai_retrieval_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("query", sa.Text(), nullable=False),
            sa.Column("role", sa.String(32), nullable=False),
            sa.Column("retrieved_chunk_ids_json", sa.Text(), nullable=True),
            sa.Column("retrieval_scores_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    for table in (
        "ai_retrieval_logs",
        "clinical_reference_embeddings",
        "clinical_reference_chunks",
        "clinical_reference_documents",
        "clinical_snapshot_feedback",
        "clinical_snapshots",
    ):
        if has_table(table):
            op.drop_table(table)
