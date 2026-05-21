"""incident_messages table

Revision ID: v1w2x3y4z5a6
Revises: u1v2w3x4y5z6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "v1w2x3y4z5a6"
down_revision: Union[str, None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incident_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id"), nullable=False, index=True),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    op.create_index("ix_incident_messages_incident_id", "incident_messages", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_incident_messages_incident_id", table_name="incident_messages")
    op.drop_table("incident_messages")
