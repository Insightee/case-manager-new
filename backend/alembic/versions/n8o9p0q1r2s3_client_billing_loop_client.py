"""Client billing loop: package cycles, external refs, ISSUED/CLOSED status, LATE_FEE.

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-08-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "n8o9p0q1r2s3"
down_revision: Union[str, None] = "m7n8o9p0q1r2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_enum_value(enum_name: str, value: str) -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(sa.text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def upgrade() -> None:
    for value in ("ISSUED", "CLOSED"):
        _pg_enum_value("clientinvoicestatus", value)

    if not has_table("client_package_cycles"):
        op.create_table(
            "client_package_cycles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("care_package_id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("cycle_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("billed_sessions", sa.Integer(), nullable=False),
            sa.Column("consumed_sessions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("remaining_sessions", sa.Integer(), nullable=False),
            sa.Column("carry_forward_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expires_on", sa.Date(), nullable=True),
            sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("billing_mode", sa.String(length=32), nullable=False, server_default="PACKAGE"),
            sa.Column("client_invoice_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["care_package_id"], ["care_packages.id"]),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.ForeignKeyConstraint(["client_invoice_id"], ["client_invoices.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_client_package_cycles_case_id", "client_package_cycles", ["case_id"])
        op.create_index("ix_client_package_cycles_care_package_id", "client_package_cycles", ["care_package_id"])

    if not has_table("external_refs"):
        op.create_table(
            "external_refs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("external_id", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "entity_type", "entity_id", name="uq_external_refs_provider_entity"),
        )
        op.create_index("ix_external_refs_entity", "external_refs", ["entity_type", "entity_id"])

    if has_table("client_payments"):
        bind = op.get_bind()
        cols = {c["name"] for c in sa.inspect(bind).get_columns("client_payments")}
        if "gateway_provider" not in cols:
            op.add_column("client_payments", sa.Column("gateway_provider", sa.String(length=32), nullable=True))
        if "gateway_payment_id" not in cols:
            op.add_column("client_payments", sa.Column("gateway_payment_id", sa.String(length=128), nullable=True))
        if "provider_ref" not in cols:
            op.add_column("client_payments", sa.Column("provider_ref", sa.String(length=128), nullable=True))


def downgrade() -> None:
    if has_table("client_payments"):
        bind = op.get_bind()
        cols = {c["name"] for c in sa.inspect(bind).get_columns("client_payments")}
        for col in ("provider_ref", "gateway_payment_id", "gateway_provider"):
            if col in cols:
                op.drop_column("client_payments", col)

    if has_table("external_refs"):
        op.drop_index("ix_external_refs_entity", table_name="external_refs")
        op.drop_table("external_refs")

    if has_table("client_package_cycles"):
        op.drop_index("ix_client_package_cycles_care_package_id", table_name="client_package_cycles")
        op.drop_index("ix_client_package_cycles_case_id", table_name="client_package_cycles")
        op.drop_table("client_package_cycles")

    # Enum values ISSUED/CLOSED are additive-only on Postgres; downgrade leaves them in place.
