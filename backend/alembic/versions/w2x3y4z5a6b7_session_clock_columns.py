"""session clock columns: slot_duration_minutes + GPS checkin/checkout

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: 2026-05-20 23:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "w2x3y4z5a6b7"
down_revision = "v1w2x3y4z5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("slot_duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("checkin_lat", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("checkin_lng", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("checkout_lat", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("checkout_lng", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("checkout_lng")
        batch_op.drop_column("checkout_lat")
        batch_op.drop_column("checkin_lng")
        batch_op.drop_column("checkin_lat")
        batch_op.drop_column("slot_duration_minutes")
