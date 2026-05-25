"""Client payment claims — proof upload and admin confirmation.

Revision ID: f8b9c0d1e2f3
Revises: e6f7a8b9c0d1
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8b9c0d1e2f3"
down_revision: Union[str, None] = ("e6f7a8b9c0d1", "a1b2c3d4e5f7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    payment_status = sa.Enum(
        "PENDING_REVIEW",
        "CONFIRMED",
        "REJECTED",
        name="clientpaymentstatus",
    )
    payment_status.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("client_payments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "payment_status",
                payment_status,
                nullable=False,
                server_default="CONFIRMED",
            )
        )
        batch_op.add_column(sa.Column("submitted_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("proof_file_path", sa.String(512), nullable=True))
        batch_op.add_column(sa.Column("proof_file_name", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("confirmed_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("rejection_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("client_payments") as batch_op:
        batch_op.drop_column("rejection_note")
        batch_op.drop_column("confirmed_at")
        batch_op.drop_column("confirmed_by_user_id")
        batch_op.drop_column("proof_file_name")
        batch_op.drop_column("proof_file_path")
        batch_op.drop_column("submitted_by_user_id")
        batch_op.drop_column("payment_status")
