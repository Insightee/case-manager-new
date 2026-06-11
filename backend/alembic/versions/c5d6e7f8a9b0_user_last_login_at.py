"""Add users.last_login_at for portal activation tracking.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-06-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("users", "last_login_at"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    # Parents/staff who already had passwords are treated as having logged in before.
    op.execute(
        sa.text(
            "UPDATE users SET last_login_at = created_at "
            "WHERE last_login_at IS NULL AND password_hash IS NOT NULL AND password_hash != ''"
        )
    )


def downgrade() -> None:
    if _has_column("users", "last_login_at"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("last_login_at")
