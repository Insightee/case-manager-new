"""case billing address and flat pay share

Revision ID: z9b0c1d2e3f5
Revises: c5d6e7f8a9b0
Create Date: 2026-06-15 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text, inspect

from migration_util import has_column, has_table

revision: str = "z9b0c1d2e3f5"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    
    # 1. Add columns to cases
    with op.batch_alter_table("cases", schema=None) as batch_op:
        if not has_column("cases", "service_location_type"):
            batch_op.add_column(sa.Column("service_location_type", sa.String(length=32), nullable=True))
        if not has_column("cases", "billing_address_same_as_service"):
            batch_op.add_column(sa.Column("billing_address_same_as_service", sa.Boolean(), nullable=False, server_default=sa.true()))
        if not has_column("cases", "billing_address_line1"):
            batch_op.add_column(sa.Column("billing_address_line1", sa.String(length=255), nullable=True))
        if not has_column("cases", "billing_address_line2"):
            batch_op.add_column(sa.Column("billing_address_line2", sa.String(length=255), nullable=True))
        if not has_column("cases", "billing_address_city"):
            batch_op.add_column(sa.Column("billing_address_city", sa.String(length=128), nullable=True))
        if not has_column("cases", "billing_address_state"):
            batch_op.add_column(sa.Column("billing_address_state", sa.String(length=128), nullable=True))
        if not has_column("cases", "billing_address_pincode"):
            batch_op.add_column(sa.Column("billing_address_pincode", sa.String(length=16), nullable=True))
        if not has_column("cases", "billing_address_landmark"):
            batch_op.add_column(sa.Column("billing_address_landmark", sa.String(length=255), nullable=True))
        if not has_column("cases", "pay_share_amount_inr"):
            batch_op.add_column(sa.Column("pay_share_amount_inr", sa.Numeric(precision=12, scale=2), nullable=True))

    # 2. Backfill pay_share_amount_inr from pay_share_pct
    if has_column("cases", "pay_share_pct") and has_column("cases", "pay_share_amount_inr"):
        # For PER_SESSION: client_rate_per_session_inr * (pay_share_pct / 100)
        # For PACKAGE: package_amount_inr * (pay_share_pct / 100)
        op.execute(
            text(
                """
                UPDATE cases
                SET pay_share_amount_inr = client_rate_per_session_inr * (pay_share_pct / 100.0)
                WHERE billing_type = 'PER_SESSION' AND pay_share_pct IS NOT NULL AND client_rate_per_session_inr IS NOT NULL
                """
            )
        )
        op.execute(
            text(
                """
                UPDATE cases
                SET pay_share_amount_inr = package_amount_inr * (pay_share_pct / 100.0)
                WHERE billing_type = 'PACKAGE' AND pay_share_pct IS NOT NULL AND package_amount_inr IS NOT NULL
                """
            )
        )

    # 3. Drop pay_share_pct column
    with op.batch_alter_table("cases", schema=None) as batch_op:
        if has_column("cases", "pay_share_pct"):
            batch_op.drop_column("pay_share_pct")


def downgrade() -> None:
    with op.batch_alter_table("cases", schema=None) as batch_op:
        if not has_column("cases", "pay_share_pct"):
            batch_op.add_column(sa.Column("pay_share_pct", sa.Numeric(precision=5, scale=2), nullable=True))

    # Re-backfill pay_share_pct from pay_share_amount_inr
    # PER_SESSION: pay_share_amount_inr / client_rate_per_session_inr * 100
    # PACKAGE: pay_share_amount_inr / package_amount_inr * 100
    op.execute(
        text(
            """
            UPDATE cases
            SET pay_share_pct = (pay_share_amount_inr / client_rate_per_session_inr) * 100.0
            WHERE billing_type = 'PER_SESSION' AND pay_share_amount_inr IS NOT NULL AND client_rate_per_session_inr > 0
            """
        )
    )
    op.execute(
        text(
            """
            UPDATE cases
            SET pay_share_pct = (pay_share_amount_inr / package_amount_inr) * 100.0
            WHERE billing_type = 'PACKAGE' AND pay_share_amount_inr IS NOT NULL AND package_amount_inr > 0
            """
        )
    )

    with op.batch_alter_table("cases", schema=None) as batch_op:
        if has_column("cases", "pay_share_amount_inr"):
            batch_op.drop_column("pay_share_amount_inr")
        if has_column("cases", "billing_address_landmark"):
            batch_op.drop_column("billing_address_landmark")
        if has_column("cases", "billing_address_pincode"):
            batch_op.drop_column("billing_address_pincode")
        if has_column("cases", "billing_address_state"):
            batch_op.drop_column("billing_address_state")
        if has_column("cases", "billing_address_city"):
            batch_op.drop_column("billing_address_city")
        if has_column("cases", "billing_address_line2"):
            batch_op.drop_column("billing_address_line2")
        if has_column("cases", "billing_address_line1"):
            batch_op.drop_column("billing_address_line1")
        if has_column("cases", "billing_address_same_as_service"):
            batch_op.drop_column("billing_address_same_as_service")
        if has_column("cases", "service_location_type"):
            batch_op.drop_column("service_location_type")
