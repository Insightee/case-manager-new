"""Merge billing engine tip with therapist-profile pending head.

Revision ID: c2d3e4f5a6b7
Revises: a4b5c6d7e8f9, tp_pending_sub_2606
Create Date: 2026-08-02

"""
from typing import Sequence, Union

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = ("a4b5c6d7e8f9", "tp_pending_sub_2606")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
