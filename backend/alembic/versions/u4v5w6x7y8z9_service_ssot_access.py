"""Service SSOT: shadow_support id, access grants, service products, access_group.

Revision ID: u4v5w6x7y8z9
Revises: t2u3v4w5x6y7
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u4v5w6x7y8z9"
down_revision: Union[str, None] = "t2u3v4w5x6y7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CANONICAL_SEED = [
    ("shadow_support", "Shadow support", 0),
    ("homecare", "Homecare", 1),
    ("occupational_therapy", "Occupational therapy", 2),
    ("speech_therapy", "Speech therapy", 3),
    ("special_educator", "Special educator", 4),
    ("behavior_therapy", "Behavior therapy", 5),
    ("play_therapy", "Play therapy", 6),
    ("customised_employment", "Customised employment", 7),
    ("subject_tutor", "Subject tutor", 8),
    ("sports", "Sports", 9),
    ("counselling", "Counselling", 10),
]


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("service_categories"):
        cols = {c["name"] for c in insp.get_columns("service_categories")}
        if "access_group" not in cols:
            op.add_column(
                "service_categories",
                sa.Column("access_group", sa.String(64), nullable=False, server_default="Clinical"),
            )
        if "product_modules" not in cols:
            op.add_column("service_categories", sa.Column("product_modules", sa.JSON(), nullable=True))

        # Migrate legacy shadow -> shadow_support
        row = conn.execute(sa.text("SELECT id FROM service_categories WHERE id = 'shadow'")).first()
        existing_ss = conn.execute(
            sa.text("SELECT id FROM service_categories WHERE id = 'shadow_support'")
        ).first()
        if row and not existing_ss:
            conn.execute(
                sa.text(
                    "UPDATE service_categories SET id = 'shadow_support', label = 'Shadow support' WHERE id = 'shadow'"
                )
            )
        elif row and existing_ss:
            conn.execute(
                sa.text("UPDATE service_categories SET is_active = :active WHERE id = 'shadow'"),
                {"active": False},
            )

        for sid, label, order in _CANONICAL_SEED:
            pm = json.dumps([{"id": sid, "label": label}])
            existing = conn.execute(
                sa.text("SELECT id FROM service_categories WHERE id = :id"), {"id": sid}
            ).first()
            if existing:
                conn.execute(
                    sa.text(
                        "UPDATE service_categories SET label = :label, sort_order = :order, "
                        "is_active = :active, access_group = 'Clinical', product_modules = :pm WHERE id = :id"
                    ),
                    {"id": sid, "label": label, "order": order, "pm": pm, "active": True},
                )
            else:
                conn.execute(
                    sa.text(
                        "INSERT INTO service_categories (id, label, sort_order, is_active, access_group, product_modules) "
                        "VALUES (:id, :label, :order, :active, 'Clinical', :pm)"
                    ),
                    {"id": sid, "label": label, "order": order, "pm": pm, "active": True},
                )

    user_cols = {c["name"] for c in insp.get_columns("users")} if insp.has_table("users") else set()
    if "service_access_grants" not in user_cols:
        op.add_column("users", sa.Column("service_access_grants", sa.JSON(), nullable=True))
    if "org_capability_grants" not in user_cols:
        op.add_column("users", sa.Column("org_capability_grants", sa.JSON(), nullable=True))

    if not insp.has_table("service_products"):
        op.create_table(
            "service_products",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("service_category_id", sa.String(64), sa.ForeignKey("service_categories.id"), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("billing_model", sa.String(32), nullable=False),
            sa.Column("price_inr", sa.Numeric(12, 2), nullable=True),
            sa.Column("package_sessions", sa.Integer(), nullable=True),
            sa.Column("discount_percent", sa.Numeric(5, 2), nullable=True),
            sa.Column("total_inr", sa.Numeric(12, 2), nullable=True),
            sa.Column("taxable", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("gst_rate_percent", sa.Numeric(5, 2), nullable=True),
            sa.Column("gst_split", sa.String(16), nullable=True),
            sa.Column("leave_policy", sa.String(32), nullable=True),
            sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
            sa.Column("product_billing_rule_id", sa.Integer(), sa.ForeignKey("product_billing_rules.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_service_products_category", "service_products", ["service_category_id"])

    memo_cols = {c["name"] for c in insp.get_columns("memos")} if insp.has_table("memos") else set()
    if insp.has_table("memos") and "email_sent_at" not in memo_cols:
        op.add_column("memos", sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True))
    if insp.has_table("memos") and "send_as_email" not in memo_cols:
        op.add_column("memos", sa.Column("send_as_email", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("memos", "send_as_email")
    op.drop_column("memos", "email_sent_at")
    op.drop_table("service_products")
    op.drop_column("users", "org_capability_grants")
    op.drop_column("users", "service_access_grants")
    op.drop_column("service_categories", "access_group")
