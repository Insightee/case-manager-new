"""Clinical Brain phases 2B-5: feedback, review queue, parent inputs, evidence snapshots.

Revision ID: e4f5a6b7c8d9
Revises: d2e3f4a5b6c7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("strategy_recommendation_feedback"):
        op.create_table(
            "strategy_recommendation_feedback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("child_id", sa.Integer(), sa.ForeignKey("children.id"), nullable=True),
            sa.Column("goal_repository_item_id", sa.Integer(), sa.ForeignKey("goal_repository_items.id"), nullable=True),
            sa.Column("goal_card_id", sa.Integer(), sa.ForeignKey("iep_goal_cards.id"), nullable=True),
            sa.Column("strategy_repository_item_id", sa.Integer(), sa.ForeignKey("strategy_repository_items.id"), nullable=True),
            sa.Column("recommendation_source", sa.String(32), nullable=False, server_default="library_match"),
            sa.Column("feedback_status", sa.String(32), nullable=False),
            sa.Column("adaptation_text", sa.Text(), nullable=True),
            sa.Column("dismissal_reason", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_by_role", sa.String(32), nullable=True),
            sa.Column("source_context_json", sa.Text(), nullable=True),
            sa.Column("parent_visible", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("review_status", sa.String(32), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_srf_case_id", "strategy_recommendation_feedback", ["case_id"])
        op.create_index("ix_srf_strategy_id", "strategy_recommendation_feedback", ["strategy_repository_item_id"])

    if not has_table("clinical_review_queue_items"):
        op.create_table(
            "clinical_review_queue_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("item_type", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
            sa.Column("source_case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("source_goal_id", sa.Integer(), nullable=True),
            sa.Column("source_strategy_id", sa.Integer(), nullable=True),
            sa.Column("linked_library_goal_id", sa.Integer(), nullable=True),
            sa.Column("linked_library_strategy_id", sa.Integer(), nullable=True),
            sa.Column("source_entity_kind", sa.String(32), nullable=True),
            sa.Column("source_entity_id", sa.Integer(), nullable=True),
            sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reviewer_note", sa.Text(), nullable=True),
            sa.Column("action_payload_json", sa.Text(), nullable=True),
            sa.Column("title", sa.String(255), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("parent_safe", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_crqi_case_status", "clinical_review_queue_items", ["source_case_id", "status"])

    if not has_table("clinical_review_queue_events"):
        op.create_table(
            "clinical_review_queue_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("queue_item_id", sa.Integer(), sa.ForeignKey("clinical_review_queue_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("old_status", sa.String(32), nullable=True),
            sa.Column("new_status", sa.String(32), nullable=False),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("parent_goal_inputs"):
        op.create_table(
            "parent_goal_inputs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("goal_ref", sa.String(64), nullable=False),
            sa.Column("input_type", sa.String(64), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("parent_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("review_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_parent_goal_inputs_case", "parent_goal_inputs", ["case_id"])

    if not has_table("monthly_report_evidence_snapshots"):
        op.create_table(
            "monthly_report_evidence_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("report_id", sa.Integer(), nullable=True),
            sa.Column("clinical_report_id", sa.Integer(), sa.ForeignKey("clinical_reports.id"), nullable=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("month", sa.String(7), nullable=False),
            sa.Column("evidence_json", sa.Text(), nullable=False),
            sa.Column("source_hash", sa.String(64), nullable=False),
            sa.Column("compiler_version", sa.String(16), nullable=False, server_default="1.0.0"),
            sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("generated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        )
        op.create_index("ix_mres_report_month", "monthly_report_evidence_snapshots", ["case_id", "month"])

    for col_name, col_type in (
        ("task_type", sa.String(64)),
        ("report_id", sa.Integer()),
        ("goal_id", sa.Integer()),
        ("prompt_version", sa.String(32)),
        ("input_summary_json", sa.Text()),
        ("output_text", sa.Text()),
        ("output_json", sa.Text()),
        ("token_input_count", sa.Integer()),
        ("token_output_count", sa.Integer()),
        ("estimated_cost", sa.Numeric(12, 6)),
        ("status", sa.String(32)),
        ("safety_flags_json", sa.Text()),
        ("source_ids_json", sa.Text()),
    ):
        if has_table("ai_generation_logs") and not has_column("ai_generation_logs", col_name):
            op.add_column("ai_generation_logs", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    for table in (
        "monthly_report_evidence_snapshots",
        "parent_goal_inputs",
        "clinical_review_queue_events",
        "clinical_review_queue_items",
        "strategy_recommendation_feedback",
    ):
        if has_table(table):
            op.drop_table(table)
