"""Force remaining PERCENTAGE cases to FIXED_LUMP.

Revision ID: k2pct2lumpfix
Revises: k1shadow2lumpsum3
Create Date: 2026-08-28

k1shadow2lumpsum3 skipped PERCENTAGE rows where therapist_fixed_pay_inr was
already set but differed from pay_share_amount_inr. Prefer the fixed column
(already INR) and flip mode only — never re-multiply.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "k2pct2lumpfix"
down_revision: Union[str, None] = "k1shadow2lumpsum3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Prefer existing fixed amount; flip mode.
    op.execute(
        text(
            """
            UPDATE cases
            SET compensation_mode = 'FIXED_LUMP'
            WHERE compensation_mode = 'PERCENTAGE'
              AND therapist_fixed_pay_inr IS NOT NULL
              AND therapist_fixed_pay_inr > 0
            """
        )
    )

    # Remaining PERCENTAGE with share only → copy into fixed (amounts already INR).
    op.execute(
        text(
            """
            UPDATE cases
            SET therapist_fixed_pay_inr = pay_share_amount_inr,
                compensation_mode = 'FIXED_LUMP'
            WHERE compensation_mode = 'PERCENTAGE'
              AND pay_share_amount_inr IS NOT NULL
              AND pay_share_amount_inr > 0
              AND (
                therapist_fixed_pay_inr IS NULL
                OR therapist_fixed_pay_inr = 0
              )
            """
        )
    )

    # Keep share column aligned for legacy readers (fixed is source of truth).
    op.execute(
        text(
            """
            UPDATE cases
            SET pay_share_amount_inr = therapist_fixed_pay_inr
            WHERE compensation_mode = 'FIXED_LUMP'
              AND therapist_fixed_pay_inr IS NOT NULL
              AND therapist_fixed_pay_inr > 0
              AND (
                pay_share_amount_inr IS NULL
                OR pay_share_amount_inr = 0
                OR pay_share_amount_inr <> therapist_fixed_pay_inr
              )
            """
        )
    )


def downgrade() -> None:
    # Irreversible data cleanup — no-op.
    pass
