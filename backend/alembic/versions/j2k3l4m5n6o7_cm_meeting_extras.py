"""CM meeting link and guest emails

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2026-05-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j2k3l4m5n6o7"
down_revision: Union[str, None] = "i1j2k3l4m5n6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("case_manager_meetings", sa.Column("meeting_url", sa.String(512), nullable=True))
    op.add_column("case_manager_meetings", sa.Column("guest_emails_json", sa.Text(), nullable=True))
    op.add_column("therapist_profiles", sa.Column("license_number", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("therapist_profiles", "license_number")
    op.drop_column("case_manager_meetings", "guest_emails_json")
    op.drop_column("case_manager_meetings", "meeting_url")
