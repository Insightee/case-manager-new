"""Additive: therapist_statement_disputes resolve columns.

Revision ID: b8c9d0e1f2a4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-04

Purely additive — adds finance resolution metadata columns. No engine/ledger touch.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_column, has_table

revision: str = "b8c9d0e1f2a4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("therapist_statement_disputes"):
        return
    if not has_column("therapist_statement_disputes", "prior_invoice_status"):
        op.add_column(
            "therapist_statement_disputes",
            sa.Column("prior_invoice_status", sa.String(length=32), nullable=True),
        )
    if not has_column("therapist_statement_disputes", "admin_resolution"):
        op.add_column(
            "therapist_statement_disputes",
            sa.Column("admin_resolution", sa.Text(), nullable=True),
        )
    if not has_column("therapist_statement_disputes", "resolved_at"):
        op.add_column(
            "therapist_statement_disputes",
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not has_column("therapist_statement_disputes", "resolved_by_user_id"):
        op.add_column(
            "therapist_statement_disputes",
            sa.Column(
                "resolved_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    if not has_table("therapist_statement_disputes"):
        return
    if has_column("therapist_statement_disputes", "resolved_by_user_id"):
        op.drop_column("therapist_statement_disputes", "resolved_by_user_id")
    if has_column("therapist_statement_disputes", "resolved_at"):
        op.drop_column("therapist_statement_disputes", "resolved_at")
    if has_column("therapist_statement_disputes", "admin_resolution"):
        op.drop_column("therapist_statement_disputes", "admin_resolution")
    if has_column("therapist_statement_disputes", "prior_invoice_status"):
        op.drop_column("therapist_statement_disputes", "prior_invoice_status")
