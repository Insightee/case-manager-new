"""Therapist module reliability: session auto-end, leave case link, CM completion, invoice manual lines."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e3"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("auto_end_reason", sa.String(64), nullable=True))
    op.add_column("therapist_leaves", sa.Column("case_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_therapist_leaves_case_id",
        "therapist_leaves",
        "cases",
        ["case_id"],
        ["id"],
    )
    op.create_index("ix_therapist_leaves_case_id", "therapist_leaves", ["case_id"])

    op.add_column(
        "case_manager_meetings",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "case_manager_meetings",
        sa.Column("completed_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cm_meetings_completed_by",
        "case_manager_meetings",
        "users",
        ["completed_by_user_id"],
        ["id"],
    )

    op.create_table(
        "invoice_manual_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True, index=True),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("amount_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column("pay_share_inr", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("added_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column(
        "client_invoice_lines",
        sa.Column("approval_status", sa.String(32), nullable=True),
    )
    op.add_column(
        "client_invoice_lines",
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_client_invoice_lines_approved_by",
        "client_invoice_lines",
        "users",
        ["approved_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_client_invoice_lines_approved_by", "client_invoice_lines", type_="foreignkey")
    op.drop_column("client_invoice_lines", "approved_by_user_id")
    op.drop_column("client_invoice_lines", "approval_status")
    op.drop_table("invoice_manual_lines")
    op.drop_constraint("fk_cm_meetings_completed_by", "case_manager_meetings", type_="foreignkey")
    op.drop_column("case_manager_meetings", "completed_by_user_id")
    op.drop_column("case_manager_meetings", "completed_at")
    op.drop_index("ix_therapist_leaves_case_id", table_name="therapist_leaves")
    op.drop_constraint("fk_therapist_leaves_case_id", "therapist_leaves", type_="foreignkey")
    op.drop_column("therapist_leaves", "case_id")
    op.drop_column("sessions", "auto_end_reason")
