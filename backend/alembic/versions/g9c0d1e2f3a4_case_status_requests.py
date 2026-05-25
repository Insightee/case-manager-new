"""Case status change requests from therapists.

Revision ID: g9c0d1e2f3a4
Revises: f8b9c0d1e2f3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g9c0d1e2f3a4"
down_revision: Union[str, None] = "f8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status_enum = sa.Enum("PENDING", "APPROVED", "REJECTED", name="casestatusrequeststatus")
    status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "case_status_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=False),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_status_requests_case_id", "case_status_requests", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_status_requests_case_id", "case_status_requests")
    op.drop_table("case_status_requests")
