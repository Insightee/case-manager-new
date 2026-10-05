"""parent meeting requests

Revision ID: pmr7req20261005
Revises: i2all3cases4fin
Create Date: 2026-10-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from migration_util import has_table

revision: str = "pmr7req20261005"
down_revision: Union[str, None] = "i2all3cases4fin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("parent_meeting_requests"):
        return

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                """
                DO $$ BEGIN
                    CREATE TYPE parentmeetingrequeststatus AS ENUM ('PENDING', 'FULFILLED', 'DISMISSED');
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )
        status_type = sa.Enum(
            "PENDING",
            "FULFILLED",
            "DISMISSED",
            name="parentmeetingrequeststatus",
            create_type=False,
        )
    else:
        status_type = sa.Enum("PENDING", "FULFILLED", "DISMISSED", name="parentmeetingrequeststatus")

    op.create_table(
        "parent_meeting_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("parent_user_id", sa.Integer(), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("requested_date", sa.Date(), nullable=False),
        sa.Column("status", status_type, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parent_meeting_requests_case_id", "parent_meeting_requests", ["case_id"])
    op.create_index("ix_parent_meeting_requests_parent_user_id", "parent_meeting_requests", ["parent_user_id"])
    op.create_index("ix_parent_meeting_requests_therapist_user_id", "parent_meeting_requests", ["therapist_user_id"])
    op.create_index("ix_parent_meeting_requests_status", "parent_meeting_requests", ["status"])


def downgrade() -> None:
    if not has_table("parent_meeting_requests"):
        return
    op.drop_index("ix_parent_meeting_requests_status", table_name="parent_meeting_requests")
    op.drop_index("ix_parent_meeting_requests_therapist_user_id", table_name="parent_meeting_requests")
    op.drop_index("ix_parent_meeting_requests_parent_user_id", table_name="parent_meeting_requests")
    op.drop_index("ix_parent_meeting_requests_case_id", table_name="parent_meeting_requests")
    op.drop_table("parent_meeting_requests")
