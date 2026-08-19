"""Repair goal/strategy repository columns when c7r8e9p0o1r2 created minimal tables.

Revision ID: d8r9e0p1o2r3
Revises: c7r8e9p0o1r2
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "d8r9e0p1o2r3"
down_revision: Union[str, None] = "c7r8e9p0o1r2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GOAL_REPO_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    (
        "source_daily_log_id",
        sa.Column("source_daily_log_id", sa.Integer(), sa.ForeignKey("daily_logs.id"), nullable=True),
    ),
    ("source_session_id", sa.Column("source_session_id", sa.Integer(), nullable=True)),
    ("review_note", sa.Column("review_note", sa.Text(), nullable=True)),
    ("core_domains_json", sa.Column("core_domains_json", sa.Text(), nullable=True)),
    ("core_environments_json", sa.Column("core_environments_json", sa.Text(), nullable=True)),
    ("baseline_state", sa.Column("baseline_state", sa.Text(), nullable=True)),
    ("desired_state", sa.Column("desired_state", sa.Text(), nullable=True)),
    ("goal_statement", sa.Column("goal_statement", sa.Text(), nullable=True)),
    ("lifecycle_status", sa.Column("lifecycle_status", sa.String(length=32), nullable=True)),
    ("source", sa.Column("source", sa.String(length=32), nullable=True)),
    ("scope", sa.Column("scope", sa.String(length=32), nullable=True)),
    (
        "source_clinical_report_id",
        sa.Column(
            "source_clinical_report_id",
            sa.Integer(),
            sa.ForeignKey("clinical_reports.id"),
            nullable=True,
        ),
    ),
)

_STRATEGY_REPO_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    ("domain_key", sa.Column("domain_key", sa.String(length=64), nullable=True)),
    ("environment_context", sa.Column("environment_context", sa.String(length=32), nullable=True)),
    (
        "linked_goal_card_id",
        sa.Column(
            "linked_goal_card_id",
            sa.Integer(),
            sa.ForeignKey("iep_goal_cards.id"),
            nullable=True,
        ),
    ),
    (
        "source_daily_log_id",
        sa.Column("source_daily_log_id", sa.Integer(), sa.ForeignKey("daily_logs.id"), nullable=True),
    ),
    ("review_note", sa.Column("review_note", sa.Text(), nullable=True)),
    ("core_domains_json", sa.Column("core_domains_json", sa.Text(), nullable=True)),
    ("core_environments_json", sa.Column("core_environments_json", sa.Text(), nullable=True)),
    ("strategy_steps_json", sa.Column("strategy_steps_json", sa.Text(), nullable=True)),
    ("expected_outcome", sa.Column("expected_outcome", sa.Text(), nullable=True)),
    ("source", sa.Column("source", sa.String(length=32), nullable=True)),
    ("scope", sa.Column("scope", sa.String(length=32), nullable=True)),
    (
        "source_clinical_report_id",
        sa.Column(
            "source_clinical_report_id",
            sa.Integer(),
            sa.ForeignKey("clinical_reports.id"),
            nullable=True,
        ),
    ),
)


def _add_missing_columns(table: str, columns: tuple[tuple[str, sa.Column], ...]) -> None:
    if not has_table(table):
        return
    for name, column in columns:
        if not has_column(table, name):
            op.add_column(table, column)


def upgrade() -> None:
    _add_missing_columns("goal_repository_items", _GOAL_REPO_COLUMNS)
    _add_missing_columns("strategy_repository_items", _STRATEGY_REPO_COLUMNS)


def downgrade() -> None:
    for name, _ in reversed(_STRATEGY_REPO_COLUMNS):
        if has_column("strategy_repository_items", name):
            op.drop_column("strategy_repository_items", name)
    for name, _ in reversed(_GOAL_REPO_COLUMNS):
        if has_column("goal_repository_items", name):
            op.drop_column("goal_repository_items", name)
