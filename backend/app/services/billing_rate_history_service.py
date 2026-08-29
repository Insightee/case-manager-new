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


def amounts_changed(*, previous: dict, proposed: dict, case_after: Case | dict) -> tuple[bool, bool]:
    _ = proposed
    prev_client = _money(client_amount_inr(previous))
    new_client = _money(client_amount_inr(case_after))
    prev_therapist = _money(resolve_therapist_pay(previous))
    new_therapist = _money(resolve_therapist_pay(case_after))
    return prev_client != new_client, prev_therapist != new_therapist


def _sync_client_rate_period(
    db: Session,
    *,
    case: Case,
    new_rate: float,
    effective_from: date,
    changed_by_user_id: int,
) -> None:
    """Keep Step-6 case_client_rate_periods aligned with billing rate history."""
    from datetime import timedelta

    from app.models.billing_step6 import CaseClientRatePeriod

    open_rows = list(
        db.scalars(
            select(CaseClientRatePeriod).where(
                CaseClientRatePeriod.case_id == case.id,
                CaseClientRatePeriod.end_date.is_(None),
            )
        ).all()
    )
    for row in open_rows:
        if row.start_date < effective_from:
            row.end_date = effective_from - timedelta(days=1)
        elif row.start_date >= effective_from:
            row.end_date = row.start_date
    db.add(
        CaseClientRatePeriod(
            case_id=case.id,
            start_date=effective_from,
            end_date=None,
            rate_inr=new_rate,
            label="normal",
            effective_date_choice="CHANGE_DATE",
            resolved_effective_date=effective_from,
            created_by_user_id=changed_by_user_id,
            notes="Synced from case_billing_rate_changes",
        )
    )


def record_rate_change(
    db: Session,
    *,
    case: Case,
    previous: dict,
    proposed: dict,
    changed_by_user_id: int,
    source: str = "FORM",
    audit_event_id: int | None = None,
    therapist_user_id: int | None = None,
    require_effective_dates: bool = True,
) -> CaseBillingRateChange | None:
    """Persist an immutable rate-change row when client and/or therapist amounts move.

    FORM saves require explicit effective dates so payout/invoice months stay correct.
    Backfill may set require_effective_dates=False only when dates are already resolved.
    """
    from app.core.billing_validation import case_billing_dict

    client_changed, therapist_changed = amounts_changed(
        previous=previous, proposed=proposed, case_after=case
    )
    if not client_changed and not therapist_changed:
        return None

    client_eff = _coerce_date(proposed.get("client_billing_effective_from"))
    therapist_eff = _coerce_date(proposed.get("therapist_remuneration_effective_from"))

    if require_effective_dates:
        missing: list[str] = []
        if client_changed and client_eff is None:
            missing.append("client billing effective from")
        if therapist_changed and therapist_eff is None:
            missing.append("therapist remuneration effective from")
        if missing:
            prev_c = _money(client_amount_inr(previous)) or 0.0
            prev_t = _money(resolve_therapist_pay(previous)) or 0.0
            if prev_c == 0.0 and prev_t == 0.0:
                today = date.today()
                if client_changed and client_eff is None:
                    client_eff = today
                if therapist_changed and therapist_eff is None:
                    therapist_eff = today
            else:
                raise ValueError(
                    "Looks like we still need the "
                    + " and ".join(missing)
                    + " date(s) before we can save this rate change."
                )

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
        source=source,
        audit_event_id=audit_event_id,
        therapist_user_id=therapist_user_id,
        changed_by_user_id=changed_by_user_id,
    )
    db.add(row)
    db.flush()

    if client_changed and client_eff is not None and new_client is not None and source == "FORM":
        _sync_client_rate_period(
            db,
            case=case,
            new_rate=float(new_client),
            effective_from=client_eff,
            changed_by_user_id=changed_by_user_id,
        )
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
                # Case-level history only (assignment-scoped rows handled separately).
                CaseBillingRateChange.therapist_user_id.is_(None),
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


def resolve_therapist_pay_for_assignment(
    db: Session,
    case: Case,
    *,
    assignment: Any | None,
    as_of: date | None = None,
) -> float:
    """Pay for a therapist×case segment.

    Outgoing / ended assignments with a frozen billing_snapshot keep that locked share
    so a later case hike (new therapist remun) does not rewrite the prior therapist's month.
    Active assignments use case-level as-of history.
    """
    snap = getattr(assignment, "billing_snapshot", None) if assignment is not None else None
    if isinstance(snap, dict) and snap:
        locked = resolve_therapist_pay(snap)
        if locked > 0:
            return locked
    return resolve_therapist_pay_as_of(db, case, as_of)


def ensure_effective_dates_for_amount_change(*, previous: dict, proposed: dict, merged: dict) -> None:
    """Raise before apply/request when amount moves lack applicable-from dates.

    Initial billing setup (previous client + therapist both zero) may omit dates;
    record_rate_change will default those to today.
    """
    client_changed, therapist_changed = amounts_changed(
        previous=previous, proposed=proposed, case_after=merged
    )
    if not client_changed and not therapist_changed:
        return
    prev_c = _money(client_amount_inr(previous)) or 0.0
    prev_t = _money(resolve_therapist_pay(previous)) or 0.0
    if prev_c == 0.0 and prev_t == 0.0:
        return
    client_eff = _coerce_date(proposed.get("client_billing_effective_from"))
    therapist_eff = _coerce_date(proposed.get("therapist_remuneration_effective_from"))
    missing: list[str] = []
    if client_changed and client_eff is None:
        missing.append("client billing effective from")
    if therapist_changed and therapist_eff is None:
        missing.append("therapist remuneration effective from")
    if missing:
        raise ValueError(
            "Looks like we still need the "
            + " and ".join(missing)
            + " date(s) before we can save this rate change."
        )


def insert_historical_rate_change(
    db: Session,
    *,
    case_id: int,
    previous: dict,
    new_billing: dict,
    effective_from: date,
    changed_by_user_id: int,
    audit_event_id: int,
    source: str = "AUDIT_BACKFILL",
) -> CaseBillingRateChange | None:
    """Insert rate history from audit snapshots without mutating cases or invoices.

    Idempotent on audit_event_id. Does not sync Step-6 client rate periods.
    """
    existing = db.scalars(
        select(CaseBillingRateChange).where(CaseBillingRateChange.audit_event_id == audit_event_id)
    ).first()
    if existing:
        return None

    client_changed, therapist_changed = amounts_changed(
        previous=previous, proposed=new_billing, case_after=new_billing
    )
    if not client_changed and not therapist_changed:
        return None

    prev_client = _money(client_amount_inr(previous))
    new_client = _money(client_amount_inr(new_billing))
    prev_therapist = _money(resolve_therapist_pay(previous))
    new_therapist = _money(resolve_therapist_pay(new_billing))

    row = CaseBillingRateChange(
        case_id=case_id,
        previous_client_amount_inr=prev_client if client_changed else None,
        new_client_amount_inr=new_client if client_changed else None,
        previous_therapist_amount_inr=prev_therapist if therapist_changed else None,
        new_therapist_amount_inr=new_therapist if therapist_changed else None,
        client_effective_from=effective_from if client_changed else None,
        therapist_effective_from=effective_from if therapist_changed else None,
        previous_snapshot={k: v for k, v in previous.items() if k not in BILLING_META_KEYS},
        new_snapshot={k: v for k, v in new_billing.items() if k not in BILLING_META_KEYS},
        notes=(
            new_billing.get("billing_notes")
            if isinstance(new_billing.get("billing_notes"), str)
            else None
        ),
        source=source,
        audit_event_id=audit_event_id,
        changed_by_user_id=changed_by_user_id or 1,
    )
    db.add(row)
    db.flush()
    return row


def _audit_new_billing_payload(new_value: Any) -> dict | None:
    if not isinstance(new_value, dict):
        return None
    if new_value.get("applied") is False:
        return None
    for key in ("proposed_billing", "applied_billing"):
        payload = new_value.get(key)
        if isinstance(payload, dict):
            return payload
    # Some older audits may store billing fields at the top level.
    if any(
        k in new_value
        for k in (
            "billing_type",
            "client_rate_per_session_inr",
            "therapist_fixed_pay_inr",
            "pay_share_amount_inr",
            "package_amount_inr",
            "client_monthly_rate_inr",
        )
    ):
        return new_value
    return None


def backfill_rate_history_from_audits(
    db: Session,
    *,
    dry_run: bool = True,
    case_id: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Reconstruct case_billing_rate_changes from applied billing audit events.

    Safety:
    - INSERT only (never updates cases, invoices, settlements, or Step-6 periods)
    - Idempotent via unique audit_event_id
    - Skips pending approval audits (applied=false) and unparseable payloads
    - effective_from = audit created_at calendar date (IST)
    """
    from zoneinfo import ZoneInfo

    from app.models.audit_event import AuditEvent
    import json

    ist = ZoneInfo("Asia/Kolkata")
    actions = ("update_billing", "approve_low_margin_billing")
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.action.in_(actions))
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    )
    if case_id is not None:
        stmt = stmt.where(AuditEvent.case_id == case_id)
    if limit is not None:
        stmt = stmt.limit(limit)

    events = list(db.scalars(stmt).all())
    inserted = 0
    skipped = 0
    samples: list[dict[str, Any]] = []

    for ev in events:
        if ev.case_id is None:
            skipped += 1
            continue
        try:
            old_value = json.loads(ev.old_value) if ev.old_value else {}
        except (TypeError, json.JSONDecodeError):
            old_value = {}
        try:
            new_value = json.loads(ev.new_value) if ev.new_value else {}
        except (TypeError, json.JSONDecodeError):
            skipped += 1
            continue
        if not isinstance(old_value, dict):
            old_value = {}
        new_billing = _audit_new_billing_payload(new_value)
        if not new_billing:
            skipped += 1
            continue

        created = ev.created_at
        if created is None:
            skipped += 1
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=ZoneInfo("UTC"))
        effective_from = created.astimezone(ist).date()

        already = db.scalars(
            select(CaseBillingRateChange).where(CaseBillingRateChange.audit_event_id == ev.id)
        ).first()
        if already:
            skipped += 1
            continue

        client_changed, therapist_changed = amounts_changed(
            previous=old_value, proposed=new_billing, case_after=new_billing
        )
        if not client_changed and not therapist_changed:
            skipped += 1
            continue

        sample = {
            "audit_event_id": ev.id,
            "case_id": ev.case_id,
            "action": ev.action,
            "effective_from": effective_from.isoformat(),
            "client_changed": client_changed,
            "therapist_changed": therapist_changed,
            "previous_client": _money(client_amount_inr(old_value)),
            "new_client": _money(client_amount_inr(new_billing)),
            "previous_therapist": _money(resolve_therapist_pay(old_value)),
            "new_therapist": _money(resolve_therapist_pay(new_billing)),
        }
        if len(samples) < 40:
            samples.append(sample)

        if dry_run:
            inserted += 1
            continue

        row = insert_historical_rate_change(
            db,
            case_id=int(ev.case_id),
            previous=old_value,
            new_billing=new_billing,
            effective_from=effective_from,
            changed_by_user_id=int(ev.actor_user_id or 1),
            audit_event_id=int(ev.id),
        )
        if row:
            inserted += 1
        else:
            skipped += 1

    return {
        "dry_run": dry_run,
        "scanned": len(events),
        "inserted_or_would_insert": inserted,
        "skipped": skipped,
        "samples": samples,
    }


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
