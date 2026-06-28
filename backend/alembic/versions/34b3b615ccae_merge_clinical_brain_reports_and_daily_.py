"""merge clinical brain reports and daily_logs repair heads

Revision ID: 34b3b615ccae
Revises: e4f5a6b7c8d9, r2s3t4u5v6w7, v6w7x8y9z0a1
Create Date: 2026-06-28 22:43:53.161839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '34b3b615ccae'
down_revision: Union[str, None] = ('e4f5a6b7c8d9', 'r2s3t4u5v6w7', 'v6w7x8y9z0a1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
