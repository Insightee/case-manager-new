"""report rich text columns and report_images

Revision ID: a1b2c3d4e5f7
Revises: z0a1b2c3d4e5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "z0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("monthly_reports", "observation_reports"):
        op.add_column(table, sa.Column("body_html", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("plan_next_month", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("category", sa.String(32), nullable=True))
        op.add_column(table, sa.Column("sub_category", sa.String(32), nullable=True))
        op.add_column(table, sa.Column("report_date", sa.Date(), nullable=True))

    op.execute("UPDATE monthly_reports SET category = 'CLIENT_MONTHLY' WHERE category IS NULL")

    op.create_table(
        "report_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_type", sa.String(16), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_report_images_report", "report_images", ["report_type", "report_id"])


def downgrade() -> None:
    op.drop_index("ix_report_images_report", table_name="report_images")
    op.drop_table("report_images")
    for table in ("observation_reports", "monthly_reports"):
        op.drop_column(table, "report_date")
        op.drop_column(table, "sub_category")
        op.drop_column(table, "category")
        op.drop_column(table, "plan_next_month")
        op.drop_column(table, "body_html")
