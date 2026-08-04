"""Additive: therapist_statement_disputes (therapist-side statement flag).

Revision ID: a7d9f2c4e6b8
Revises: n8o9p0q1r2s3
Create Date: 2026-08-03

Purely additive — creates ONE new standalone table and alters nothing else.
No engine/ledger schema is touched. Downgrade drops the table cleanly.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "a7d9f2c4e6b8"
down_revision: Union[str, None] = "n8o9p0q1r2s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("therapist_statement_disputes"):
        return
    op.create_table(
        "therapist_statement_disputes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "therapist_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("month", sa.String(length=32), nullable=False, index=True),
        sa.Column(
            "invoice_id",
            sa.Integer(),
            sa.ForeignKey("invoices.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("disputed_session_ids", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    if has_table("therapist_statement_disputes"):
        op.drop_table("therapist_statement_disputes")
