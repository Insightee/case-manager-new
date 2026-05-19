"""homecare_addresses

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-20 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("home_address_line1", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("home_address_line2", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("home_city", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("home_state", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("home_pincode", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("home_landmark", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("home_latitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("home_longitude", sa.Float(), nullable=True))

    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(sa.Column("service_address_line1", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("service_address_line2", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("service_city", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("service_state", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("service_pincode", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("service_landmark", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("service_latitude", sa.Float(), nullable=True))
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
