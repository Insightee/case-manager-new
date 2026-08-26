"""Add integration clients, credentials, case grants; audit actor column.

Revision ID: i1integr2api3layer
Revises: i0merge1integration
Create Date: 2026-08-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i1integr2api3layer"
down_revision: Union[str, Sequence[str], None] = "i0merge1integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_integration_clients_status", "integration_clients", ["status"])

    op.create_table(
        "integration_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "integration_client_id",
            sa.Integer(),
            sa.ForeignKey("integration_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("public_client_id", sa.String(length=64), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("public_client_id", name="uq_integration_credentials_public_client_id"),
    )
    op.create_index(
        "ix_integration_credentials_client_id",
        "integration_credentials",
        ["integration_client_id"],
    )

    op.create_table(
        "integration_case_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "integration_client_id",
            sa.Integer(),
            sa.ForeignKey("integration_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "integration_client_id",
            "case_id",
            name="uq_integration_case_grants_client_case",
        ),
    )
    op.create_index(
        "ix_integration_case_grants_case_id",
        "integration_case_grants",
        ["case_id"],
    )

    op.add_column(
        "audit_events",
        sa.Column(
            "integration_client_id",
            sa.Integer(),
            sa.ForeignKey("integration_clients.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_audit_events_integration_client_id",
        "audit_events",
        ["integration_client_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_integration_client_id", table_name="audit_events")
    op.drop_column("audit_events", "integration_client_id")
    op.drop_index("ix_integration_case_grants_case_id", table_name="integration_case_grants")
    op.drop_table("integration_case_grants")
    op.drop_index("ix_integration_credentials_client_id", table_name="integration_credentials")
    op.drop_table("integration_credentials")
    op.drop_index("ix_integration_clients_status", table_name="integration_clients")
    op.drop_table("integration_clients")
