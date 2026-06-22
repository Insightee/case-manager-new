"""add session dispute and report ratings

Revision ID: c6b1725843e6
Revises: o1p2q3r4s5t6
Create Date: 2026-06-22 15:41:00.308114

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c6b1725843e6'
down_revision: Union[str, None] = 'o1p2q3r4s5t6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from migration_util import has_column


def upgrade() -> None:
    if not has_column("support_tickets", "disputed_session_id"):
        op.add_column("support_tickets", sa.Column("disputed_session_id", sa.Integer(), nullable=True))
    if not has_column("monthly_reports", "parent_monthly_rating"):
        op.add_column("monthly_reports", sa.Column("parent_monthly_rating", sa.Integer(), nullable=True))


def downgrade() -> None:
    if has_column("monthly_reports", "parent_monthly_rating"):
        op.drop_column("monthly_reports", "parent_monthly_rating")
    if has_column("support_tickets", "disputed_session_id"):
        op.drop_column("support_tickets", "disputed_session_id")
