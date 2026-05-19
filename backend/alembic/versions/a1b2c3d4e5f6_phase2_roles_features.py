"""phase2_roles_features

Revision ID: a1b2c3d4e5f6
Revises: 70ed65093b89
Create Date: 2026-05-19 14:00:00.000000

Adds: employment_status + location on users, category on support_tickets,
therapist_leaves table, therapist_slots table, memos table.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "70ed65093b89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: add employment_status and location ---
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "employment_status",
                sa.Enum("ACTIVE", "SUSPENDED", "ARCHIVED", name="employmentstatus"),
                nullable=False,
                server_default="ACTIVE",
            )
        )
        batch_op.add_column(sa.Column("location", sa.String(255), nullable=True))

    # --- support_tickets: add category ---
    with op.batch_alter_table("support_tickets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "category",
                sa.Enum("FINANCE", "HR", "SERVICE", "POSH", "CPP", "OTHER", name="ticketcategory"),
                nullable=False,
                server_default="OTHER",
            )
        )

    # --- therapist_leaves ---
    op.create_table(
        "therapist_leaves",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("therapist_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column(
            "leave_type",
            sa.Enum("ANNUAL", "SICK", "CASUAL", "UNPAID", name="leavetype"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", "CANCELLED", name="leavestatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("reviewed_by_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- therapist_slots ---
    op.create_table(
        "therapist_slots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("therapist_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("slot_date", sa.Date, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column(
            "status",
            sa.Enum("AVAILABLE", "BOOKED", "BLOCKED", name="slotstatus"),
            nullable=False,
            server_default="AVAILABLE",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- memos ---
    op.create_table(
        "memos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("from_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_user_ids", sa.JSON, nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("memos")
    op.drop_table("therapist_slots")
    op.drop_table("therapist_leaves")

    with op.batch_alter_table("support_tickets") as batch_op:
        batch_op.drop_column("category")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("location")
        batch_op.drop_column("employment_status")
