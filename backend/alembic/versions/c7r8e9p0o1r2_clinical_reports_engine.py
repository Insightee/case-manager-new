"""Clinical reports engine + goal repository (carve from report-overhaul; chains after structured evidence).

Revision ID: c7r8e9p0o1r2
Revises: s4e5v6i7d8e9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_column, has_table

revision: str = "c7r8e9p0o1r2"
down_revision: Union[str, None] = "s4e5v6i7d8e9"
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

    if not has_table("clinical_reports"):
        op.create_table(
            "clinical_reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("child_id", sa.Integer(), sa.ForeignKey("children.id"), nullable=True),
            sa.Column("report_type", sa.String(32), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("current_version_id", sa.Integer(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("assigned_therapist_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("case_manager_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("parent_visible_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        )
        create_index_if_missing("ix_clinical_reports_case_id", "clinical_reports", ["case_id"])
        create_index_if_missing("ix_clinical_reports_report_type", "clinical_reports", ["report_type"])
        create_index_if_missing("ix_clinical_reports_status", "clinical_reports", ["status"])

    if not has_table("clinical_report_versions"):
        op.create_table(
            "clinical_report_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "report_id",
                sa.Integer(),
                sa.ForeignKey("clinical_reports.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("snapshot_json", sa.Text(), nullable=True),
            sa.Column("change_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_clinical_report_versions_report_id", "clinical_report_versions", ["report_id"])

    if not has_table("clinical_report_sections"):
        op.create_table(
            "clinical_report_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "report_id",
                sa.Integer(),
                sa.ForeignKey("clinical_reports.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("section_key", sa.String(64), nullable=False),
            sa.Column("section_title", sa.String(255), nullable=False),
            sa.Column("section_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("structured_data_json", sa.Text(), nullable=True),
            sa.Column("narrative_text", sa.Text(), nullable=True),
            sa.Column("internal_notes", sa.Text(), nullable=True),
            sa.Column("completion_status", sa.String(32), nullable=False, server_default="not_started"),
            sa.Column("visibility", sa.String(32), nullable=False, server_default="clinical_team"),
            sa.Column("evidence_refs_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_clinical_report_sections_report_id", "clinical_report_sections", ["report_id"])
        create_index_if_missing("ix_clinical_report_sections_section_key", "clinical_report_sections", ["section_key"])

    if not has_table("clinical_report_evidence"):
        op.create_table(
            "clinical_report_evidence",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "report_id",
                sa.Integer(),
                sa.ForeignKey("clinical_reports.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column("source_type", sa.String(64), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("section_key", sa.String(64), nullable=True),
            sa.Column("evidence_label", sa.String(255), nullable=True),
            sa.Column("visibility", sa.String(32), nullable=False, server_default="clinical_team"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_clinical_report_evidence_report_id", "clinical_report_evidence", ["report_id"])

    if not has_table("clinical_report_review_events"):
        op.create_table(
            "clinical_report_review_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "report_id",
                sa.Integer(),
                sa.ForeignKey("clinical_reports.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("actor_role", sa.String(64), nullable=True),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing(
            "ix_clinical_report_review_events_report_id",
            "clinical_report_review_events",
            ["report_id"],
        )

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

    if has_table("observation_checklists") and not has_column("observation_checklists", "clinical_report_id"):
        op.add_column(
            "observation_checklists",
            sa.Column("clinical_report_id", sa.Integer(), sa.ForeignKey("clinical_reports.id"), nullable=True),
        )
        create_index_if_missing(
            "ix_observation_checklists_clinical_report_id",
            "observation_checklists",
            ["clinical_report_id"],
        )

    if has_table("goal_repository_items") and not has_column("goal_repository_items", "source_clinical_report_id"):
        op.add_column(
            "goal_repository_items",
            sa.Column("source_clinical_report_id", sa.Integer(), sa.ForeignKey("clinical_reports.id"), nullable=True),
        )

    if has_table("strategy_repository_items") and not has_column("strategy_repository_items", "source_clinical_report_id"):
        op.add_column(
            "strategy_repository_items",
            sa.Column("source_clinical_report_id", sa.Integer(), sa.ForeignKey("clinical_reports.id"), nullable=True),
        )


def downgrade() -> None:
    if has_column("strategy_repository_items", "source_clinical_report_id"):
        op.drop_column("strategy_repository_items", "source_clinical_report_id")
    if has_column("goal_repository_items", "source_clinical_report_id"):
        op.drop_column("goal_repository_items", "source_clinical_report_id")
    if has_column("observation_checklists", "clinical_report_id"):
        op.drop_column("observation_checklists", "clinical_report_id")

    for table in (
        "goal_evidence_events",
        "iep_support_priorities",
        "iep_goal_cards",
        "clinical_report_review_events",
        "clinical_report_evidence",
        "clinical_report_sections",
        "clinical_report_versions",
        "clinical_reports",
        "strategy_repository_items",
        "goal_repository_items",
    ):
        if has_table(table):
            op.drop_table(table)
