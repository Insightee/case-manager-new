from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.billing_validation import (
    BILLING_META_KEYS,
    client_amount_inr,
    resolve_therapist_pay,
)
from app.models.case import Case
from app.models.case_billing_rate_change import CaseBillingRateChange


def _coerce_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()[:10]
    if not text:
        return None
    return date.fromisoformat(text)


def _money(value: object) -> float | None:
    if value in (None, ""):
        return None
    return round(float(value), 2)


def amounts_changed(*, previous: dict, proposed: dict, case_after: Case) -> tuple[bool, bool]:
    _ = proposed
    prev_client = _money(client_amount_inr(previous))
    new_client = _money(client_amount_inr(case_after))
    prev_therapist = _money(resolve_therapist_pay(previous))
    new_therapist = _money(resolve_therapist_pay(case_after))
    return prev_client != new_client, prev_therapist != new_therapist


def record_rate_change(
    db: Session,
    *,
    case: Case,
    previous: dict,
    proposed: dict,
    changed_by_user_id: int,
) -> CaseBillingRateChange | None:
    """Persist an immutable rate-change row when client and/or therapist amounts move."""
    from app.core.billing_validation import case_billing_dict

    client_changed, therapist_changed = amounts_changed(
        previous=previous, proposed=proposed, case_after=case
    )
    if not client_changed and not therapist_changed:
        return None

    client_eff = _coerce_date(proposed.get("client_billing_effective_from"))
    therapist_eff = _coerce_date(proposed.get("therapist_remuneration_effective_from"))
    today = date.today()

    if client_changed and client_eff is None:
        client_eff = today
    if therapist_changed and therapist_eff is None:
        therapist_eff = today

    prev_client = _money(client_amount_inr(previous))
    new_client = _money(client_amount_inr(case))
    prev_therapist = _money(resolve_therapist_pay(previous))
    new_therapist = _money(resolve_therapist_pay(case))

    row = CaseBillingRateChange(
        case_id=case.id,
        previous_client_amount_inr=prev_client if client_changed else None,
        new_client_amount_inr=new_client if client_changed else None,
        previous_therapist_amount_inr=prev_therapist if therapist_changed else None,
        new_therapist_amount_inr=new_therapist if therapist_changed else None,
        client_effective_from=client_eff if client_changed else None,
        therapist_effective_from=therapist_eff if therapist_changed else None,
        previous_snapshot={k: v for k, v in previous.items() if k not in BILLING_META_KEYS},
        new_snapshot=case_billing_dict(case),
        notes=(proposed.get("billing_notes") if isinstance(proposed.get("billing_notes"), str) else None)
        or (previous.get("billing_notes") if isinstance(previous.get("billing_notes"), str) else None),
        changed_by_user_id=changed_by_user_id,
    )
    db.add(row)
    db.flush()
    return row


def resolve_therapist_pay_as_of(db: Session, case: Case, as_of: date | None = None) -> float:
    """Therapist remuneration applicable on as_of (service/invoice period), not live case only."""
    day = as_of or date.today()
    rows = list(
        db.scalars(
            select(CaseBillingRateChange)
            .where(
                CaseBillingRateChange.case_id == case.id,
                CaseBillingRateChange.therapist_effective_from.is_not(None),
            )
            .order_by(
                CaseBillingRateChange.therapist_effective_from.asc(),
                CaseBillingRateChange.id.asc(),
            )
        ).all()
    )
    if not rows:
        return resolve_therapist_pay(case)

    applicable = [r for r in rows if r.therapist_effective_from and r.therapist_effective_from <= day]
    if applicable:
        latest = applicable[-1]
        if latest.new_therapist_amount_inr is not None:
            return float(latest.new_therapist_amount_inr)
        return resolve_therapist_pay(case)

    # as_of is before the first scheduled hike — use the previous amount on that first change.
    first = rows[0]
    if first.previous_therapist_amount_inr is not None:
        return float(first.previous_therapist_amount_inr)
    return resolve_therapist_pay(case)


def resolve_client_amount_as_of(db: Session, case: Case, as_of: date | None = None) -> float:
    day = as_of or date.today()
    rows = list(
        db.scalars(
            select(CaseBillingRateChange)
            .where(
                CaseBillingRateChange.case_id == case.id,
                CaseBillingRateChange.client_effective_from.is_not(None),
            )
            .order_by(
                CaseBillingRateChange.client_effective_from.asc(),
                CaseBillingRateChange.id.asc(),
            )
        ).all()
    )
    if not rows:
        return client_amount_inr(case)

    applicable = [r for r in rows if r.client_effective_from and r.client_effective_from <= day]
    if applicable:
        latest = applicable[-1]
        if latest.new_client_amount_inr is not None:
            return float(latest.new_client_amount_inr)
        return client_amount_inr(case)

    first = rows[0]
    if first.previous_client_amount_inr is not None:
        return float(first.previous_client_amount_inr)
    return client_amount_inr(case)


def format_rate_change_detail(row: CaseBillingRateChange, *, for_therapist: bool = False) -> str:
    parts: list[str] = []
    if row.previous_client_amount_inr is not None or row.new_client_amount_inr is not None:
        eff = row.client_effective_from.isoformat() if row.client_effective_from else "—"
        parts.append(
            f"Client billing ₹{float(row.previous_client_amount_inr or 0):.0f} → "
            f"₹{float(row.new_client_amount_inr or 0):.0f} (from {eff})"
        )
    if row.previous_therapist_amount_inr is not None or row.new_therapist_amount_inr is not None:
        eff = row.therapist_effective_from.isoformat() if row.therapist_effective_from else "—"
        parts.append(
            f"Therapist remuneration ₹{float(row.previous_therapist_amount_inr or 0):.0f} → "
            f"₹{float(row.new_therapist_amount_inr or 0):.0f} (from {eff})"
        )
    if for_therapist:
        # Therapists see client billing + remuneration amount changes only (no full snapshot dump).
        return "; ".join(parts) if parts else "Billing amounts updated"
    if row.notes:
        parts.append(f"Notes: {row.notes[:160]}")
    return "; ".join(parts) if parts else "Billing amounts updated"


def timeline_events_for_case(
    db: Session,
    case_id: int,
    *,
    for_therapist: bool = False,
    limit: int = 40,
) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(CaseBillingRateChange)
            .where(CaseBillingRateChange.case_id == case_id)
            .order_by(CaseBillingRateChange.created_at.desc(), CaseBillingRateChange.id.desc())
            .limit(limit)
        ).all()
    )
    events: list[dict[str, Any]] = []
    for row in rows:
        if for_therapist and (
            row.previous_client_amount_inr is None
            and row.new_client_amount_inr is None
            and row.previous_therapist_amount_inr is None
            and row.new_therapist_amount_inr is None
        ):
            continue
        eff = row.therapist_effective_from or row.client_effective_from
        events.append(
            {
                "source": "billing_rate",
                "id": f"billing-rate-{row.id}",
                "action": "billing_rate_change",
                "action_label": "Billing amount change",
                "detail": format_rate_change_detail(row, for_therapist=for_therapist),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "effective_date": eff.isoformat() if eff else None,
                "entity_type": "case_billing_rate_change",
                "entity_id": str(row.id),
                "case_id": case_id,
            }
        )
    return events
