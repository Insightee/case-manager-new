"""integration key permissions and webhooks

Revision ID: bb6328f4ca05
Revises: st1ff4tt3nd1
Create Date: 2026-09-24 08:15:21.565148

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bb6328f4ca05"
down_revision: Union[str, None] = "st1ff4tt3nd1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "integration_clients",
        sa.Column("access_token_minutes", sa.Integer(), nullable=False, server_default="15"),
    )
    op.add_column(
        "integration_clients",
        sa.Column("key_ttl_days", sa.Integer(), nullable=False, server_default="365"),
    )
    op.add_column(
        "integration_clients",
        sa.Column("mcp_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "integration_webhooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("integration_client_id", sa.Integer(), sa.ForeignKey("integration_clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=False),
        sa.Column("events_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_integration_webhooks_client", "integration_webhooks", ["integration_client_id"])
    op.create_table(
        "integration_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("integration_client_id", sa.Integer(), sa.ForeignKey("integration_clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("signal_key", sa.String(length=64), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_integration_signals_client", "integration_signals", ["integration_client_id"])
    op.create_index("ix_integration_signals_case", "integration_signals", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_integration_signals_case", table_name="integration_signals")
    op.drop_index("ix_integration_signals_client", table_name="integration_signals")
    op.drop_table("integration_signals")
    op.drop_index("ix_integration_webhooks_client", table_name="integration_webhooks")
    op.drop_table("integration_webhooks")
    op.drop_column("integration_clients", "mcp_enabled")
    op.drop_column("integration_clients", "key_ttl_days")
    op.drop_column("integration_clients", "access_token_minutes")
