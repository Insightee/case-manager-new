"""Merge divergent Alembic heads before integration API schema.

Revision ID: i0merge1integration
Revises: all current heads
Create Date: 2026-08-26

Production migrate_production.py and alembic/env.py require a single head.
"""
from typing import Sequence, Union

revision: str = "i0merge1integration"
down_revision: Union[str, Sequence[str], None] = (
    "a7d9f2c4e6b8",
    "b2c3d4e5f6g7",
    "b3c4d5e6f7a8",
    "c0d1e2f3a4b6",
    "c1d2e3f4a5b6",
    "c6b1725843e6",
    "c7d8e9f0a1b2",
    "d7e8f9a0b1c2",
    "f3a4b5c6d7e9",
    "fn9tds0cl1nt",
    "m1n2o3p4q5r6",
    "m9n0o1p2q3r4",
    "o9p0q1r2s3t4",
    "p1q2r3s4t5u6",
    "p2q3r4s5t6u7",
    "r0s1t2u3v4w5",
    "v1w2x3y4z5a6",
    "x7y8z9a0b1c2",
    "z1o2h3o4i5d6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
