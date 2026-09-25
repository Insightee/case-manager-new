"""SPOT role staff employment fields and staff leave billing category."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_util import has_table

revision: str = "s7p0t3m4p5l6"
down_revision: Union[str, None] = "bb6328f4ca05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_table("users"):
        bind = op.get_bind()
        insp = sa.inspect(bind)
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "staff_employment_type" not in user_cols:
            op.add_column("users", sa.Column("staff_employment_type", sa.String(32), nullable=True))
        if "staff_probation_months" not in user_cols:
            op.add_column("users", sa.Column("staff_probation_months", sa.Integer(), nullable=True))
        if "staff_employment_start_date" not in user_cols:
            op.add_column("users", sa.Column("staff_employment_start_date", sa.Date(), nullable=True))
        if "staff_leave_credit_balance" not in user_cols:
            op.add_column(
                "users",
                sa.Column("staff_leave_credit_balance", sa.Integer(), nullable=False, server_default="0"),
            )
        if "staff_probation_end_notified_at" not in user_cols:
            op.add_column("users", sa.Column("staff_probation_end_notified_at", sa.DateTime(timezone=True), nullable=True))

    if has_table("staff_leaves"):
        bind = op.get_bind()
        insp = sa.inspect(bind)
        sl_cols = {c["name"] for c in insp.get_columns("staff_leaves")}
        if "billing_category" not in sl_cols:
            op.add_column("staff_leaves", sa.Column("billing_category", sa.String(32), nullable=True))

    if has_table("roles"):
        op.execute(
            sa.text(
                "INSERT INTO roles (name) SELECT 'SPOT' "
                "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'SPOT')"
            )
        )


def downgrade() -> None:
    if has_table("staff_leaves"):
        bind = op.get_bind()
        insp = sa.inspect(bind)
        sl_cols = {c["name"] for c in insp.get_columns("staff_leaves")}
        if "billing_category" in sl_cols:
            op.drop_column("staff_leaves", "billing_category")
    if has_table("users"):
        bind = op.get_bind()
        insp = sa.inspect(bind)
        user_cols = {c["name"] for c in insp.get_columns("users")}
        for col in (
            "staff_probation_end_notified_at",
            "staff_leave_credit_balance",
            "staff_employment_start_date",
            "staff_probation_months",
            "staff_employment_type",
        ):
            if col in user_cols:
                op.drop_column("users", col)
