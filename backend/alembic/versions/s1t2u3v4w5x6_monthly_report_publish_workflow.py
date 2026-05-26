"""Monthly report CM/admin publish workflow columns."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s1t2u3v4w5x6"
down_revision = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("monthly_reports", sa.Column("submitted_for_review_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("monthly_reports", sa.Column("cm_published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("monthly_reports", sa.Column("cm_published_by_user_id", sa.Integer(), nullable=True))
    op.add_column("monthly_reports", sa.Column("admin_published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("monthly_reports", sa.Column("admin_published_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_monthly_reports_cm_published_by",
        "monthly_reports",
        "users",
        ["cm_published_by_user_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_monthly_reports_admin_published_by",
        "monthly_reports",
        "users",
        ["admin_published_by_user_id"],
        ["id"],
    )
    # Backfill legacy parent-visible reports as CM-published
    op.execute(
        """
        UPDATE monthly_reports
        SET cm_published_at = COALESCE(updated_at, created_at)
        WHERE status = 'PUBLISHED'
          AND visibility_status IN ('APPROVED_FOR_PARENT', 'SHARED_WITH_PARENT')
          AND cm_published_at IS NULL
          AND admin_published_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_monthly_reports_admin_published_by", "monthly_reports", type_="foreignkey")
    op.drop_constraint("fk_monthly_reports_cm_published_by", "monthly_reports", type_="foreignkey")
    op.drop_column("monthly_reports", "admin_published_by_user_id")
    op.drop_column("monthly_reports", "admin_published_at")
    op.drop_column("monthly_reports", "cm_published_by_user_id")
    op.drop_column("monthly_reports", "cm_published_at")
    op.drop_column("monthly_reports", "submitted_for_review_at")
