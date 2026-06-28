"""clinical_reports engine tables + bridge FKs on observation_checklists and repository items."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import create_index_if_missing, has_column, has_table

revision: str = "v6w7x8y9z0a1"
down_revision: Union[str, None] = "u5v6w7x8y9z0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
            sa.Column("report_id", sa.Integer(), sa.ForeignKey("clinical_reports.id", ondelete="CASCADE"), nullable=False),
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
            sa.Column("report_id", sa.Integer(), sa.ForeignKey("clinical_reports.id", ondelete="CASCADE"), nullable=False),
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
            sa.Column("report_id", sa.Integer(), sa.ForeignKey("clinical_reports.id", ondelete="CASCADE"), nullable=False),
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
            sa.Column("report_id", sa.Integer(), sa.ForeignKey("clinical_reports.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("actor_role", sa.String(64), nullable=True),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        create_index_if_missing("ix_clinical_report_review_events_report_id", "clinical_report_review_events", ["report_id"])

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
        "clinical_report_review_events",
        "clinical_report_evidence",
        "clinical_report_sections",
        "clinical_report_versions",
        "clinical_reports",
    ):
        if has_table(table):
            op.drop_table(table)
