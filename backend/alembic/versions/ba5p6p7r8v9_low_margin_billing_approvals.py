"""add low-margin billing approval requests

Revision ID: ba5p6p7r8v9
Revises: pf4g5h6i7j8
Create Date: 2026-08-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "ba5p6p7r8v9"
down_revision: Union[str, None] = "pf4g5h6i7j8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO permissions (name) "
            "SELECT 'case.billing.update' "
            "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'case.billing.update')"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT roles.id, permissions.id FROM roles, permissions "
            "WHERE roles.name = 'HR' AND permissions.name = 'case.billing.update' "
            "AND NOT EXISTS ("
            "SELECT 1 FROM role_permissions rp "
            "WHERE rp.role_id = roles.id AND rp.permission_id = permissions.id"
            ")"
        )
    )
    op.create_table(
        "billing_approval_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="billingapprovalstatus"),
            nullable=False,
        ),
        sa.Column("previous_billing", sa.JSON(), nullable=False),
        sa.Column("proposed_billing", sa.JSON(), nullable=False),
        sa.Column("projected_profit_inr", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_billing_approval_requests_case_id",
        "billing_approval_requests",
        ["case_id"],
    )
    op.create_index(
        "ix_billing_approval_requests_requested_by_user_id",
        "billing_approval_requests",
        ["requested_by_user_id"],
    )
    op.create_index(
        "ix_billing_approval_requests_status",
        "billing_approval_requests",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_billing_approval_requests_status",
        table_name="billing_approval_requests",
    )
    op.drop_index(
        "ix_billing_approval_requests_requested_by_user_id",
        table_name="billing_approval_requests",
    )
    op.drop_index(
        "ix_billing_approval_requests_case_id",
        table_name="billing_approval_requests",
    )
    op.drop_table("billing_approval_requests")
    sa.Enum(name="billingapprovalstatus").drop(op.get_bind(), checkfirst=True)
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE name = 'case.billing.update')"
        )
    )
    op.execute(sa.text("DELETE FROM permissions WHERE name = 'case.billing.update'"))
