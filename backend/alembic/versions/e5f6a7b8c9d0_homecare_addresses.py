"""homecare_addresses

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-20 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    user_cols = {c["name"] for c in insp.get_columns("users")}
    case_cols = {c["name"] for c in insp.get_columns("cases")}

    with op.batch_alter_table("users") as batch_op:
        if "home_address_line1" not in user_cols:
            batch_op.add_column(sa.Column("home_address_line1", sa.String(length=255), nullable=True))
        if "home_address_line2" not in user_cols:
            batch_op.add_column(sa.Column("home_address_line2", sa.String(length=255), nullable=True))
        if "home_city" not in user_cols:
            batch_op.add_column(sa.Column("home_city", sa.String(length=128), nullable=True))
        if "home_state" not in user_cols:
            batch_op.add_column(sa.Column("home_state", sa.String(length=128), nullable=True))
        if "home_pincode" not in user_cols:
            batch_op.add_column(sa.Column("home_pincode", sa.String(length=16), nullable=True))
        if "home_landmark" not in user_cols:
            batch_op.add_column(sa.Column("home_landmark", sa.String(length=255), nullable=True))
        if "home_latitude" not in user_cols:
            batch_op.add_column(sa.Column("home_latitude", sa.Float(), nullable=True))
        if "home_longitude" not in user_cols:
            batch_op.add_column(sa.Column("home_longitude", sa.Float(), nullable=True))

    with op.batch_alter_table("cases") as batch_op:
        if "service_address_line1" not in case_cols:
            batch_op.add_column(sa.Column("service_address_line1", sa.String(length=255), nullable=True))
        if "service_address_line2" not in case_cols:
            batch_op.add_column(sa.Column("service_address_line2", sa.String(length=255), nullable=True))
        if "service_city" not in case_cols:
            batch_op.add_column(sa.Column("service_city", sa.String(length=128), nullable=True))
        if "service_state" not in case_cols:
            batch_op.add_column(sa.Column("service_state", sa.String(length=128), nullable=True))
        if "service_pincode" not in case_cols:
            batch_op.add_column(sa.Column("service_pincode", sa.String(length=16), nullable=True))
        if "service_landmark" not in case_cols:
            batch_op.add_column(sa.Column("service_landmark", sa.String(length=255), nullable=True))
        if "service_latitude" not in case_cols:
            batch_op.add_column(sa.Column("service_latitude", sa.Float(), nullable=True))
        if "service_longitude" not in case_cols:
            batch_op.add_column(sa.Column("service_longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("service_longitude")
        batch_op.drop_column("service_latitude")
        batch_op.drop_column("service_landmark")
        batch_op.drop_column("service_pincode")
        batch_op.drop_column("service_state")
        batch_op.drop_column("service_city")
        batch_op.drop_column("service_address_line2")
        batch_op.drop_column("service_address_line1")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("home_longitude")
        batch_op.drop_column("home_latitude")
        batch_op.drop_column("home_landmark")
        batch_op.drop_column("home_pincode")
        batch_op.drop_column("home_state")
        batch_op.drop_column("home_city")
        batch_op.drop_column("home_address_line2")
        batch_op.drop_column("home_address_line1")
