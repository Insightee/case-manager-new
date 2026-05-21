"""observation_reports table

Revision ID: x8y9z0a1b2c3
Revises: w2x3y4z5a6b7
Create Date: 2026-05-21 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "x8y9z0a1b2c3"
down_revision = "w2x3y4z5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observation_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("visibility_status", sa.String(32), nullable=False, server_default="INTERNAL_ONLY"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_observation_reports_case_id", "observation_reports", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_observation_reports_case_id", table_name="observation_reports")
    op.drop_table("observation_reports")
