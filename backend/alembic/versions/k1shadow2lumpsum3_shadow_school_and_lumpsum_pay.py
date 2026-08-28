"""Shadow school default + lumpsum-only therapist pay backfill.

Revision ID: k1shadow2lumpsum3
Revises: j0merge2therapist
Create Date: 2026-08-28

Copy-only migration:
- Shadow/B2B sessions with mode HOME → SCHOOL
- Shadow cases get service_location_type = school
- PERCENTAGE compensation → FIXED_LUMP by copying pay_share_amount_inr → therapist_fixed_pay_inr
  (amounts are already INR — do NOT multiply)
- Open transition pending_billing_update JSON coerced to FIXED_LUMP
"""
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "k1shadow2lumpsum3"
down_revision: Union[str, None] = "j0merge2therapist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Shadow/B2B sessions that defaulted to HOME → SCHOOL
    op.execute(
        text(
            """
            UPDATE sessions
            SET mode = 'SCHOOL'
            WHERE mode = 'HOME'
              AND case_id IN (
                SELECT id FROM cases
                WHERE lower(coalesce(product_module, '')) LIKE '%shadow%'
                   OR lower(coalesce(product_module, '')) = 'b2b'
                   OR lower(coalesce(product_module, '')) LIKE '%b2b%'
              )
            """
        )
    )

    # 2. Case-level service location for shadow
    op.execute(
        text(
            """
            UPDATE cases
            SET service_location_type = 'school'
            WHERE (
                lower(coalesce(product_module, '')) LIKE '%shadow%'
                OR lower(coalesce(product_module, '')) = 'b2b'
                OR lower(coalesce(product_module, '')) LIKE '%b2b%'
            )
            AND (
                service_location_type IS NULL
                OR lower(service_location_type) IN ('home', '')
            )
            """
        )
    )

    # 3. PERCENTAGE + share-only → FIXED_LUMP (copy, never multiply)
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

    # 4. PERCENTAGE where fixed already equals share (or share empty)
    op.execute(
        text(
            """
            UPDATE cases
            SET compensation_mode = 'FIXED_LUMP'
            WHERE compensation_mode = 'PERCENTAGE'
              AND therapist_fixed_pay_inr IS NOT NULL
              AND therapist_fixed_pay_inr > 0
              AND (
                pay_share_amount_inr IS NULL
                OR pay_share_amount_inr = therapist_fixed_pay_inr
              )
            """
        )
    )

    # 5. FIXED_LUMP with amount parked in share column
    op.execute(
        text(
            """
            UPDATE cases
            SET therapist_fixed_pay_inr = pay_share_amount_inr
            WHERE compensation_mode = 'FIXED_LUMP'
              AND (therapist_fixed_pay_inr IS NULL OR therapist_fixed_pay_inr = 0)
              AND pay_share_amount_inr IS NOT NULL
              AND pay_share_amount_inr > 0
            """
        )
    )

    # 6. Keep share column in sync for legacy readers
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

    # 7. Open therapist transitions: coerce pending_billing_update to FIXED_LUMP
    try:
        rows = bind.execute(
            text(
                """
                SELECT id, pending_billing_update
                FROM case_therapist_transitions
                WHERE status IN ('PENDING', 'IN_PROGRESS', 'OPEN', 'ACTIVE')
                   OR completed_at IS NULL
                """
            )
        ).fetchall()
    except Exception:
        rows = []

    for row in rows:
        raw = row[1]
        if not raw:
            continue
        if isinstance(raw, str):
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
        elif isinstance(raw, dict):
            payload = dict(raw)
        else:
            continue
        changed = False
        if payload.get("compensation_mode") == "PERCENTAGE":
            payload["compensation_mode"] = "FIXED_LUMP"
            changed = True
        share = payload.get("pay_share_amount_inr")
        fixed = payload.get("therapist_fixed_pay_inr")
        if (fixed is None or float(fixed or 0) <= 0) and share is not None and float(share or 0) > 0:
            payload["therapist_fixed_pay_inr"] = share
            payload["compensation_mode"] = "FIXED_LUMP"
            changed = True
        if payload.get("therapist_fixed_pay_inr") and not payload.get("pay_share_amount_inr"):
            payload["pay_share_amount_inr"] = payload["therapist_fixed_pay_inr"]
            changed = True
        if not changed:
            continue
        bind.execute(
            text(
                """
                UPDATE case_therapist_transitions
                SET pending_billing_update = :payload
                WHERE id = :id
                """
            ),
            {"id": row[0], "payload": json.dumps(payload)},
        )


def downgrade() -> None:
    # Irreversible data backfill — leave amounts intact.
    pass
