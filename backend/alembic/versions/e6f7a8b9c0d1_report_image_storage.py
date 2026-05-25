"""Report image storage metadata columns.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("report_images") as batch_op:
        batch_op.add_column(sa.Column("storage_provider", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("storage_key", sa.String(512), nullable=True))
        batch_op.add_column(sa.Column("original_filename", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("mime_type", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("size_bytes", sa.Integer(), nullable=True))
        batch_op.alter_column("file_path", existing_type=sa.String(512), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("report_images") as batch_op:
        batch_op.alter_column("file_path", existing_type=sa.String(512), nullable=False)
        batch_op.drop_column("size_bytes")
        batch_op.drop_column("mime_type")
        batch_op.drop_column("original_filename")
        batch_op.drop_column("storage_key")
        batch_op.drop_column("storage_provider")
