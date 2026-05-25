"""Observation checklist and case clinical profile.

Revision ID: h0i1j2k3l4m5
Revises: g9c0d1e2f3a4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h0i1j2k3l4m5"
down_revision: Union[str, None] = "g9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_clinical_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False, unique=True),
        sa.Column("history", sa.Text(), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("interests", sa.Text(), nullable=True),
        sa.Column("goals_summary", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_case_clinical_profiles_case_id", "case_clinical_profiles", ["case_id"])

    op.create_table(
        "observation_checklists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False, unique=True),
        sa.Column("therapist_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("section_responses_json", sa.Text(), nullable=True),
        sa.Column("due_at", sa.Date(), nullable=True),
        sa.Column("due_rule", sa.String(64), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewer_comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observation_report_id", sa.Integer(), sa.ForeignKey("observation_reports.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_observation_checklists_case_id", "observation_checklists", ["case_id"])
    op.create_index(
        "ix_observation_checklists_therapist_user_id", "observation_checklists", ["therapist_user_id"]
    )


def downgrade() -> None:
    op.drop_table("observation_checklists")
    op.drop_table("case_clinical_profiles")
