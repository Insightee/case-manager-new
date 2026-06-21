"""Reports & clinical documentation revamp — additive schema (steps 4–11).

Revision ID: r1s2t3u4v5w6
Revises: o1p2q3r4s5t6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_column, has_table

revision: str = "r1s2t3u4v5w6"
down_revision: Union[str, None] = "o1p2q3r4s5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("goal_repository_items"):
        op.create_table(
            "goal_repository_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("domain_key", sa.String(64), nullable=False),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="local"),
            sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_goal_repository_items_case_id", "goal_repository_items", ["case_id"])
        create_index_if_missing("ix_goal_repository_items_status", "goal_repository_items", ["status"])

    if not has_table("strategy_repository_items"):
        op.create_table(
            "strategy_repository_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("label", sa.String(255), nullable=False),
            sa.Column("when_to_use", sa.Text(), nullable=True),
            sa.Column("how_to_use", sa.Text(), nullable=True),
            sa.Column("avoid", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="local"),
            sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_strategy_repository_items_case_id", "strategy_repository_items", ["case_id"])

    if not has_table("iep_goal_cards"):
        op.create_table(
            "iep_goal_cards",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("iep_plan_id", sa.Integer(), sa.ForeignKey("iep_plans.id", ondelete="CASCADE"), nullable=False),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("domain_key", sa.String(64), nullable=False),
            sa.Column("priority_rank", sa.Integer(), nullable=True),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column("why_it_matters", sa.Text(), nullable=True),
            sa.Column("baseline", sa.Text(), nullable=True),
            sa.Column("goal_statement", sa.Text(), nullable=True),
            sa.Column("settings_json", sa.Text(), nullable=True),
            sa.Column("success_indicators_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("repository_item_id", sa.Integer(), sa.ForeignKey("goal_repository_items.id"), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_iep_goal_cards_iep_plan_id", "iep_goal_cards", ["iep_plan_id"])
        create_index_if_missing("ix_iep_goal_cards_case_id", "iep_goal_cards", ["case_id"])

    if not has_table("iep_support_priorities"):
        op.create_table(
            "iep_support_priorities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("iep_plan_id", sa.Integer(), sa.ForeignKey("iep_plans.id", ondelete="CASCADE"), nullable=False),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column("source", sa.String(32), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("session_goal_entries"):
        op.create_table(
            "session_goal_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("daily_log_id", sa.Integer(), sa.ForeignKey("daily_logs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("goal_card_id", sa.Integer(), sa.ForeignKey("iep_goal_cards.id"), nullable=True),
            sa.Column("goal_label", sa.Text(), nullable=False),
            sa.Column("domain_key", sa.String(64), nullable=True),
            sa.Column("support_level", sa.String(16), nullable=True),
            sa.Column("response_note", sa.Text(), nullable=True),
            sa.Column("visibility", sa.String(32), nullable=False, server_default="INTERNAL_ONLY"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_session_goal_entries_daily_log_id", "session_goal_entries", ["daily_log_id"])

    if not has_table("strategy_use_events"):
        op.create_table(
            "strategy_use_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("daily_log_id", sa.Integer(), sa.ForeignKey("daily_logs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("strategy_id", sa.Integer(), sa.ForeignKey("strategy_repository_items.id"), nullable=True),
            sa.Column("strategy_label", sa.Text(), nullable=False),
            sa.Column("outcome_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("goal_evidence_events"):
        op.create_table(
            "goal_evidence_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("domain_key", sa.String(64), nullable=True),
            sa.Column("source_type", sa.String(32), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("visibility", sa.String(32), nullable=False, server_default="INTERNAL_ONLY"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_goal_evidence_events_case_id", "goal_evidence_events", ["case_id"])

    if not has_table("monthly_report_sections"):
        op.create_table(
            "monthly_report_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("report_id", sa.Integer(), sa.ForeignKey("monthly_reports.id", ondelete="CASCADE"), nullable=False),
            sa.Column("domain_key", sa.String(64), nullable=True),
            sa.Column("section_key", sa.String(64), nullable=False),
            sa.Column("content_html", sa.Text(), nullable=True),
            sa.Column("visibility", sa.String(32), nullable=False, server_default="INTERNAL_ONLY"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("progress_report_sections"):
        op.create_table(
            "progress_report_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("report_id", sa.Integer(), sa.ForeignKey("monthly_reports.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section_key", sa.String(64), nullable=False),
            sa.Column("content_html", sa.Text(), nullable=True),
            sa.Column("visibility", sa.String(32), nullable=False, server_default="INTERNAL_ONLY"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("ai_generation_logs"):
        op.create_table(
            "ai_generation_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("provider", sa.String(32), nullable=False, server_default="mock"),
            sa.Column("model", sa.String(64), nullable=True),
            sa.Column("input_hash", sa.String(64), nullable=False),
            sa.Column("token_count", sa.Integer(), nullable=True),
            sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not has_table("ai_draft_outputs"):
        op.create_table(
            "ai_draft_outputs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("generation_log_id", sa.Integer(), sa.ForeignKey("ai_generation_logs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_type", sa.String(32), nullable=False),
            sa.Column("target_id", sa.Integer(), nullable=True),
            sa.Column("draft_text", sa.Text(), nullable=False),
            sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    for col, coltype in [
        ("linked_report_id", sa.Integer()),
        ("linked_goal_id", sa.Integer()),
        ("linked_strategy_id", sa.Integer()),
        ("domain_key", sa.String(64)),
    ]:
        if has_table("case_documents") and not has_column("case_documents", col):
            op.add_column("case_documents", sa.Column(col, coltype, nullable=True))


def downgrade() -> None:
    for col in ("linked_report_id", "linked_goal_id", "linked_strategy_id", "domain_key"):
        if has_table("case_documents") and has_column("case_documents", col):
            op.drop_column("case_documents", col)

    for table in (
        "ai_draft_outputs",
        "ai_generation_logs",
        "progress_report_sections",
        "monthly_report_sections",
        "goal_evidence_events",
        "strategy_use_events",
        "session_goal_entries",
        "iep_support_priorities",
        "iep_goal_cards",
        "strategy_repository_items",
        "goal_repository_items",
    ):
        if has_table(table):
            op.drop_table(table)
