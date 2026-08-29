"""Add source/audit linkage to case_billing_rate_changes.

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "v6w7x8y9z0a1"
down_revision: Union[str, None] = "u5v6w7x8y9z0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("case_billing_rate_changes"):
        return
    if not has_column("case_billing_rate_changes", "source"):
        with op.batch_alter_table("case_billing_rate_changes") as batch:
            batch.add_column(
                sa.Column("source", sa.String(length=32), nullable=False, server_default="FORM")
            )
            batch.add_column(sa.Column("audit_event_id", sa.Integer(), nullable=True))
            batch.add_column(sa.Column("therapist_user_id", sa.Integer(), nullable=True))
        op.create_index(
            "ix_case_billing_rate_changes_audit_event_id",
            "case_billing_rate_changes",
            ["audit_event_id"],
            unique=True,
        )
        op.create_index(
            "ix_case_billing_rate_changes_therapist_user_id",
            "case_billing_rate_changes",
            ["therapist_user_id"],
        )
        op.create_index(
            "ix_case_billing_rate_changes_source",
            "case_billing_rate_changes",
            ["source"],
        )


def downgrade() -> None:
    if not has_table("case_billing_rate_changes"):
        return
    if has_column("case_billing_rate_changes", "source"):
        op.drop_index("ix_case_billing_rate_changes_source", table_name="case_billing_rate_changes")
        op.drop_index(
            "ix_case_billing_rate_changes_therapist_user_id",
            table_name="case_billing_rate_changes",
        )
        op.drop_index(
            "ix_case_billing_rate_changes_audit_event_id",
            table_name="case_billing_rate_changes",
        )
        with op.batch_alter_table("case_billing_rate_changes") as batch:
            batch.drop_column("therapist_user_id")
            batch.drop_column("audit_event_id")
            batch.drop_column("source")
