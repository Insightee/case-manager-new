from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("insightcase.billing_ledger")

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.case import BillingType, Case, CaseStatus
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.ledger_billing import (
    BillableStatus,
    BillingLedger,
    BillingPeriodFlag,
    LedgerDisputeStatus,
    LedgerEventType,
    LedgerSourceType,
    PeriodFlagKind,
    ProductBillingModel,
    ProductBillingRule,
)
from app.models.parent import ParentGuardian, parent_child_link
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services import product_billing_rule_service
from app.services import finance_payout_preview_service as payout_cycle
from app.core.feature_flags import billing_ledger_writes_enabled

# Days-in-month divisor for monthly proration (product convention: /30).
_MONTHLY_PRORATION_DAYS = 30


def _ledger_writes_allowed() -> bool:
    """Hard gate: session/log ledger mutations off unless BILLING_LEDGER_WRITES is true.

    Unit tests (app_env=test/testing) enable writes so calculator coverage stays green
    without requiring every test to set the flag.
    """
    from app.core.config import settings

    if settings.app_env.lower() in ("test", "testing"):
        return True
    return billing_ledger_writes_enabled()


def _ledger_amounts_frozen(status: BillableStatus) -> bool:
    """Billable and invoiced rows keep rate/amount — case price changes must not rewrite history."""
    return status in (BillableStatus.BILLABLE, BillableStatus.INVOICED)



def _ledger_month(d: date) -> str:
    return d.strftime("%Y-%m")


def _month_bounds(billing_month: str) -> tuple[date, date]:
    year_s, month_s = billing_month.split("-")[:2]
    year, month = int(year_s), int(month_s)
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _inclusive_days(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end - start).days + 1


def _parent_for_case(db: Session, case: Case) -> int | None:
    row = db.execute(
        select(ParentGuardian.user_id)
        .join(parent_child_link, parent_child_link.c.parent_guardian_id == ParentGuardian.id)
        .where(parent_child_link.c.child_id == case.child_id)
        .limit(1)
    ).first()
    return row[0] if row else None


def _resolve_rule(db: Session, case: Case) -> ProductBillingRule | None:
    if case.product_billing_rule_id:
        return product_billing_rule_service.get_rule(db, case.product_billing_rule_id)
    stmt = (
        select(ProductBillingRule)
        .where(
            ProductBillingRule.product_module == case.product_module,
            ProductBillingRule.active.is_(True),
        )
        .order_by(ProductBillingRule.id)
    )
    return db.scalars(stmt).first()


def _case_is_monthly_fixed(case: Case, rule: ProductBillingRule | None) -> bool:
    """Case.billing_type wins when set; product-rule MONTHLY_FIXED fills legacy gaps only."""
    if case.billing_type == BillingType.MONTHLY_FIXED:
        return True
    if case.billing_type in (BillingType.PER_SESSION, BillingType.PACKAGE):
        return False
    if rule and rule.billing_model == ProductBillingModel.MONTHLY_FIXED:
        return True
    return False


def _case_is_package(case: Case, rule: ProductBillingRule | None) -> bool:
    if case.billing_type == BillingType.PACKAGE:
        return True
    if case.billing_type in (BillingType.PER_SESSION, BillingType.MONTHLY_FIXED):
        return False
    if rule and rule.billing_model == ProductBillingModel.PREPAID_PACKAGE:
        return True
    return False


def _uses_calendar_day_ledger(case: Case) -> bool:
    return payout_cycle.uses_calendar_day_pay(case)


def _blocks_per_session_ledger(case: Case, rule: ProductBillingRule | None) -> bool:
    """MONTHLY_FIXED, PACKAGE, and shadow/B2B calendar-day cases never use session × rate."""
    return (
        _case_is_monthly_fixed(case, rule)
        or _case_is_package(case, rule)
        or _uses_calendar_day_ledger(case)
    )


# ---------------------------------------------------------------------------
# Effective-dated rate periods (MONTHLY_FIXED)
# Step 6 will add a mid-month "apply from…" prompt; periods already carry dates
# so that prompt can feed additional EffectiveRatePeriod rows without restructure.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectiveRatePeriod:
    start: date
    end: date  # inclusive
    rate_inr: float
    label: str  # "normal" | "retainer"


def _case_active_window(case: Case, month_start: date, month_end: date) -> tuple[date, date] | None:
    """Interim active window from case created_at / closed date (Step 6: assignment windows)."""
    created = case.created_at.date() if isinstance(case.created_at, datetime) else month_start
    active_start = max(month_start, created)
    closed_statuses = {CaseStatus.CLOSED, CaseStatus.DEACTIVATED}
    status = case.status if isinstance(case.status, CaseStatus) else CaseStatus(str(case.status))
    if status in closed_statuses and case.status_effective_date:
        active_end = min(month_end, case.status_effective_date)
    else:
        active_end = month_end
    if active_start > active_end:
        return None
    return active_start, active_end


def build_monthly_rate_periods(
    case: Case,
    *,
    month_start: date,
    month_end: date,
) -> list[EffectiveRatePeriod]:
    """Split a month into retainer + normal sub-periods. Never looks at sessions."""
    window = _case_active_window(case, month_start, month_end)
    if not window:
        return []
    active_start, active_end = window
    normal_rate = float(case.client_monthly_rate_inr or 0)
    ret_rate = float(case.retainer_rate_inr) if case.retainer_rate_inr is not None else None
    ret_start = case.retainer_start_date
    ret_end = case.retainer_end_date

    if ret_rate is None or ret_rate <= 0 or not ret_start or not ret_end:
        return [EffectiveRatePeriod(active_start, active_end, normal_rate, "normal")]

    r0 = max(active_start, ret_start)
    r1 = min(active_end, ret_end)
    periods: list[EffectiveRatePeriod] = []
    if r0 <= r1:
        if active_start < r0:
            periods.append(EffectiveRatePeriod(active_start, r0 - timedelta(days=1), normal_rate, "normal"))
        periods.append(EffectiveRatePeriod(r0, r1, ret_rate, "retainer"))
        if r1 < active_end:
            periods.append(EffectiveRatePeriod(r1 + timedelta(days=1), active_end, normal_rate, "normal"))
    else:
        periods.append(EffectiveRatePeriod(active_start, active_end, normal_rate, "normal"))
    return [p for p in periods if _inclusive_days(p.start, p.end) > 0 and p.rate_inr >= 0]


def compute_monthly_fixed_amount(
    periods: list[EffectiveRatePeriod],
    *,
    month_start: date | None = None,
    month_end: date | None = None,
) -> tuple[float, int, str]:
    """
    MONTHLY_FIXED amount from rate periods only — never session count.

    Full month (single rate, active for the whole calendar month) → flat monthly rate.
    Partial / split months → (rate / 30) × days, with total days capped at 30.
    Divisor is always 30, never calendar days-in-month.
    """
    if not periods:
        return 0.0, 0, ""

    total_days = sum(_inclusive_days(p.start, p.end) for p in periods)
    single_rate = len({p.rate_inr for p in periods}) == 1 and len({p.label for p in periods}) == 1
    covers_full_month = False
    if month_start is not None and month_end is not None and len(periods) == 1:
        covers_full_month = periods[0].start == month_start and periods[0].end == month_end

    # Full calendar month at one rate → bill the flat monthly rate (rate/30×30 = rate).
    if covers_full_month and single_rate:
        rate = periods[0].rate_inr
        note = f"full-month flat {periods[0].label}@₹{rate}/mo"
        return round(rate, 2), min(total_days, _MONTHLY_PRORATION_DAYS), note

    # Partial / retainer split: fixed /30 divisor; active days across periods capped at 30.
    amount = 0.0
    billed_days = 0
    bits: list[str] = []
    remaining_cap = _MONTHLY_PRORATION_DAYS
    for p in periods:
        raw_days = _inclusive_days(p.start, p.end)
        if raw_days <= 0 or remaining_cap <= 0:
            continue
        days = min(raw_days, remaining_cap)
        remaining_cap -= days
        billed_days += days
        part = round((p.rate_inr / _MONTHLY_PRORATION_DAYS) * days, 2)
        amount += part
        bits.append(f"{p.label}:{days}d@₹{p.rate_inr}/mo=₹{part}")
    return round(amount, 2), billed_days, "; ".join(bits)


def _per_session_rate_for_case(case: Case, rule: ProductBillingRule | None) -> float:
    """PER_SESSION branch only — callers must not use this for MONTHLY_FIXED/PACKAGE."""
    if case.client_rate_per_session_inr is not None:
        return float(case.client_rate_per_session_inr)
    if rule and rule.default_rate_inr is not None:
        return float(rule.default_rate_inr)
    return 0.0


def _amounts(amount: float, rule: ProductBillingRule | None) -> tuple[float, float | None, float | None, str | None]:
    gst_rate = float(rule.gst_rate_percent) if rule and rule.gst_applicable and rule.gst_rate_percent else None
    gst_amount = round(amount * gst_rate / 100, 2) if gst_rate else None
    hsn = rule.hsn_sac_code if rule else None
    return amount, gst_rate, gst_amount, hsn


def _existing_ledger(
    db: Session,
    *,
    source_type: LedgerSourceType,
    source_id: int,
) -> BillingLedger | None:
    return db.scalars(
        select(BillingLedger).where(
            BillingLedger.source_type == source_type,
            BillingLedger.source_id == source_id,
        )
    ).first()


def _existing_period_charge(
    db: Session,
    *,
    source_type: LedgerSourceType,
    case_id: int,
    ledger_month: str,
) -> BillingLedger | None:
    return db.scalars(
        select(BillingLedger).where(
            BillingLedger.source_type == source_type,
            BillingLedger.source_id == case_id,
            BillingLedger.case_id == case_id,
            BillingLedger.ledger_month == ledger_month,
        )
    ).first()


def count_qualifying_sessions_in_month(db: Session, *, case_id: int, billing_month: str) -> int:
    """Evidence for billable vs PENDING_FINANCE. Step 5 may refine eligibility later."""
    year_s, month_s = billing_month.split("-")[:2]
    return int(
        db.scalar(
            select(func.count(TherapySession.id)).where(
                TherapySession.case_id == case_id,
                extract("year", TherapySession.scheduled_date) == int(year_s),
                extract("month", TherapySession.scheduled_date) == int(month_s),
                TherapySession.status == SessionStatus.COMPLETED,
            )
        )
        or 0
    )


def _has_valid_completion_timestamps(session: TherapySession) -> bool:
    return session.actual_start_at is not None and session.actual_end_at is not None


def _retire_legacy_daily_log_ledger_rows(
    db: Session,
    *,
    session_id: int,
    keep_ledger_id: int | None,
) -> None:
    """Prevent double-billing: one session → one ledger row (SESSION key wins)."""
    legacy = db.scalars(
        select(BillingLedger).where(
            BillingLedger.session_id == session_id,
            BillingLedger.source_type == LedgerSourceType.DAILY_LOG,
        )
    ).all()
    for row in legacy:
        if keep_ledger_id is not None and row.id == keep_ledger_id:
            continue
        if row.billable_status == BillableStatus.INVOICED:
            continue
        db.delete(row)
    db.flush()


def upsert_from_daily_log_approved(db: Session, log: DailyLog) -> BillingLedger | None:
    """Approve flips the SESSION-keyed row PENDING_REVIEW → BILLABLE (never a DAILY_LOG duplicate)."""
    if not _ledger_writes_allowed():
        return None
    session = log.session
    if not session:
        return None
    case = session.case or db.get(Case, session.case_id)
    rule = _resolve_rule(db, case) if case else None
    if case and _blocks_per_session_ledger(case, rule):
        # Period charges live on ensure_period_charges — never session × rate.
        ensure_period_charges(db, case_id=case.id, billing_month=_ledger_month(session.scheduled_date))
        return None
    row = upsert_from_session_event(
        db,
        session,
        event_type=LedgerEventType.SESSION_COMPLETED,
        billable_default=BillableStatus.BILLABLE,
        daily_log_id=log.id,
        source_type=LedgerSourceType.SESSION,
        source_id=session.id,
    )
    if row is not None:
        _retire_legacy_daily_log_ledger_rows(db, session_id=session.id, keep_ledger_id=row.id)
    return row


def upsert_from_session_event(
    db: Session,
    session: TherapySession,
    *,
    event_type: LedgerEventType,
    billable_default: BillableStatus,
    daily_log_id: Optional[int] = None,
    source_type: LedgerSourceType = LedgerSourceType.SESSION,
    source_id: Optional[int] = None,
) -> BillingLedger | None:
    if not _ledger_writes_allowed():
        return None
    case = session.case or db.get(Case, session.case_id)
    if not case:
        return None
    rule = _resolve_rule(db, case)
    # Dual signal: case.billing_type OR product-rule MONTHLY_FIXED / PACKAGE.
    if _blocks_per_session_ledger(case, rule):
        return None

    # --- PER_SESSION branch only below this line ---
    # Canonical key: SESSION + session.id (hold and approve share one row).
    sid = source_id if source_id is not None else session.id
    if source_type != LedgerSourceType.SESSION:
        source_type = LedgerSourceType.SESSION
        sid = session.id
    existing = _existing_ledger(db, source_type=source_type, source_id=sid)
    if existing and existing.billable_status == BillableStatus.INVOICED:
        return existing

    billable = billable_default
    if event_type == LedgerEventType.CLIENT_NO_SHOW:
        billable = (
            BillableStatus.BILLABLE
            if rule and rule.client_no_show_billable
            else BillableStatus.NON_BILLABLE
        )
    elif event_type == LedgerEventType.THERAPIST_CANCEL:
        billable = (
            BillableStatus.BILLABLE
            if rule and rule.therapist_cancel_billable
            else BillableStatus.NON_BILLABLE
        )
    elif event_type == LedgerEventType.SESSION_CANCELLED:
        billable = BillableStatus.NON_BILLABLE

    from app.services import billing_step6_service as step6

    add_on_kind = step6.effective_add_on_kind(session)
    if add_on_kind is not None:
        add_rate, add_err = step6.add_on_client_amount(case, session)
        if add_err:
            step6.persist_calc_exceptions(
                db,
                case_id=case.id,
                billing_month=_ledger_month(session.scheduled_date),
                exceptions=[
                    {
                        "code": add_err,
                        "message": "Add-on session is missing a configured client rate",
                        "session_id": session.id,
                    }
                ],
            )
            return None
        rate = float(add_rate or 0)
    else:
        rate = _per_session_rate_for_case(case, rule)
    amount, gst_rate, gst_amount, hsn = _amounts(rate, rule)
    total = amount + (gst_amount or 0)
    parent_id = _parent_for_case(db, case)

    if existing:
        if _ledger_amounts_frozen(existing.billable_status):
            if daily_log_id is not None:
                existing.daily_log_id = daily_log_id
            existing.therapist_user_id = session.therapist_user_id
            db.flush()
            return existing
        existing.event_type = event_type
        existing.billable_status = billable
        existing.rate_inr = rate
        existing.amount_inr = amount
        existing.gst_rate_percent = gst_rate
        existing.gst_amount_inr = gst_amount
        existing.hsn_sac_code = hsn
        existing.total_inr = total
        existing.therapist_user_id = session.therapist_user_id
        existing.session_id = session.id
        if daily_log_id is not None:
            existing.daily_log_id = daily_log_id
        db.flush()
        return existing

    row = BillingLedger(
        case_id=case.id,
        parent_user_id=parent_id,
        therapist_user_id=session.therapist_user_id,
        product_billing_rule_id=rule.id if rule else None,
        source_type=source_type,
        source_id=sid,
        session_id=session.id,
        daily_log_id=daily_log_id,
        ledger_month=_ledger_month(session.scheduled_date),
        event_date=session.scheduled_date,
        event_type=event_type,
        billable_status=billable,
        quantity=1,
        rate_inr=rate,
        amount_inr=amount,
        gst_rate_percent=gst_rate,
        gst_amount_inr=gst_amount,
        hsn_sac_code=hsn,
        total_inr=total,
        dispute_status=LedgerDisputeStatus.NONE,
    )
    db.add(row)
    db.flush()
    return row


def _mark_existing_session_non_billable(
    db: Session,
    session: TherapySession,
    *,
    event_type: LedgerEventType,
) -> BillingLedger | None:
    """Void/hold teardown: never leave a stale BILLABLE/PENDING_REVIEW after status leave-completed."""
    existing = _existing_ledger(
        db, source_type=LedgerSourceType.SESSION, source_id=session.id
    )
    if not existing:
        return None
    if existing.billable_status == BillableStatus.INVOICED:
        return existing
    existing.event_type = event_type
    existing.billable_status = BillableStatus.NON_BILLABLE
    existing.amount_inr = 0
    existing.total_inr = 0
    existing.gst_amount_inr = 0 if existing.gst_amount_inr is not None else None
    db.flush()
    return existing


def sync_session_status(db: Session, session: TherapySession) -> BillingLedger | None:
    """
    Step 5 eligibility:
    - Timestamp-complete + confirmed → ledger row (PENDING_REVIEW hold until log approved → BILLABLE).
    - time_confirmation_required → no ledger yet (visible in needs-confirmation queue).
    - Away-from-completed / rejected log → NON_BILLABLE on the same SESSION-keyed row.
    """
    if not _ledger_writes_allowed():
        return None
    status = session.status
    if status == SessionStatus.COMPLETED:
        log = session.daily_log
        if log and log.approval_status == LogApprovalStatus.REJECTED:
            return _mark_existing_session_non_billable(
                db, session, event_type=LedgerEventType.SESSION_CANCELLED
            ) or upsert_from_session_event(
                db,
                session,
                event_type=LedgerEventType.SESSION_CANCELLED,
                billable_default=BillableStatus.NON_BILLABLE,
                daily_log_id=log.id,
            )
        if getattr(session, "time_confirmation_required", False):
            # Rule 2: needs therapist confirmation — stay out of billing until confirmed.
            return None
        if not _has_valid_completion_timestamps(session):
            return None
        if log and log.approval_status == LogApprovalStatus.APPROVED:
            return upsert_from_daily_log_approved(db, log)
        return upsert_from_session_event(
            db,
            session,
            event_type=LedgerEventType.SESSION_COMPLETED,
            billable_default=BillableStatus.PENDING_REVIEW,
            daily_log_id=log.id if log else None,
        )
    if status == SessionStatus.NO_SHOW or status == SessionStatus.CLIENT_ABSENT:
        return upsert_from_session_event(
            db,
            session,
            event_type=LedgerEventType.CLIENT_NO_SHOW,
            billable_default=BillableStatus.PENDING_REVIEW,
        )
    if status == SessionStatus.CANCELLED:
        return upsert_from_session_event(
            db,
            session,
            event_type=LedgerEventType.SESSION_CANCELLED,
            billable_default=BillableStatus.NON_BILLABLE,
        )
    if status == SessionStatus.THERAPIST_LEAVE:
        return upsert_from_session_event(
            db,
            session,
            event_type=LedgerEventType.THERAPIST_CANCEL,
            billable_default=BillableStatus.PENDING_REVIEW,
        )
    # SCHEDULED / RESCHEDULED / IN_PROGRESS after void or revert — clear prior hold/billable.
    if status in (SessionStatus.SCHEDULED, SessionStatus.RESCHEDULED, SessionStatus.IN_PROGRESS):
        return _mark_existing_session_non_billable(
            db, session, event_type=LedgerEventType.SESSION_CANCELLED
        )
    return None


def count_log_holds(
    db: Session,
    *,
    ledger_month: Optional[str] = None,
    case_id: Optional[int] = None,
) -> int:
    """PENDING_REVIEW session holds (log not approved) — distinct from PENDING_FINANCE period drafts."""
    stmt = select(func.count(BillingLedger.id)).where(
        BillingLedger.billable_status == BillableStatus.PENDING_REVIEW,
        BillingLedger.source_type == LedgerSourceType.SESSION,
    )
    if ledger_month:
        stmt = stmt.where(BillingLedger.ledger_month == ledger_month)
    if case_id:
        stmt = stmt.where(BillingLedger.case_id == case_id)
    return int(db.scalar(stmt) or 0)


def list_needs_therapist_confirmation(
    db: Session,
    *,
    therapist_user_id: Optional[int] = None,
    case_id: Optional[int] = None,
) -> list[dict]:
    """Completed sessions that require therapist time confirmation before billing eligibility."""
    stmt = (
        select(TherapySession)
        .where(
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.time_confirmation_required.is_(True),
        )
        .order_by(TherapySession.scheduled_date.desc(), TherapySession.id.desc())
    )
    if therapist_user_id is not None:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if case_id is not None:
        stmt = stmt.where(TherapySession.case_id == case_id)
    rows = db.scalars(stmt.limit(200)).all()
    return [
        {
            "sessionId": s.id,
            "caseId": s.case_id,
            "therapistUserId": s.therapist_user_id,
            "scheduledDate": s.scheduled_date.isoformat(),
            "status": s.status.value,
            "timeConfirmationRequired": True,
            "needsTherapistConfirmation": True,
            "message": "Needs therapist confirmation before billing eligibility",
        }
        for s in rows
    ]


def eligibility_exceptions_summary(
    db: Session,
    *,
    ledger_month: Optional[str] = None,
    case_id: Optional[int] = None,
) -> dict:
    holds = count_log_holds(db, ledger_month=ledger_month, case_id=case_id)
    needs_confirm = list_needs_therapist_confirmation(db, case_id=case_id)
    return {
        "logHoldCount": holds,
        "logHoldStatus": BillableStatus.PENDING_REVIEW.value,
        "needsTherapistConfirmationCount": len(needs_confirm),
        "needsTherapistConfirmation": needs_confirm,
        "pendingFinanceNote": (
            "PENDING_FINANCE remains Step 2 period-charge drafts — not counted here"
        ),
    }


def list_ledger(
    db: Session,
    *,
    ledger_month: Optional[str] = None,
    case_id: Optional[int] = None,
    billable_status: Optional[str] = None,
) -> list[dict]:
    stmt = select(BillingLedger).options(selectinload(BillingLedger.case)).order_by(
        BillingLedger.event_date.desc(), BillingLedger.id.desc()
    )
    if ledger_month:
        stmt = stmt.where(BillingLedger.ledger_month == ledger_month)
    if case_id:
        stmt = stmt.where(BillingLedger.case_id == case_id)
    if billable_status:
        stmt = stmt.where(BillingLedger.billable_status == BillableStatus(billable_status.upper()))
    rows = db.scalars(stmt.limit(500)).all()
    return [_serialize_ledger(r, include_finance=True) for r in rows]


def override_billable(
    db: Session,
    ledger_id: int,
    *,
    billable_status: str,
    override_reason: str,
    user_id: int,
) -> dict:
    row = db.get(BillingLedger, ledger_id)
    if not row:
        raise ValueError("Ledger row not found")
    if row.billable_status == BillableStatus.INVOICED:
        raise ValueError("Cannot override invoiced ledger row")
    row.billable_status = BillableStatus(billable_status.upper())
    row.override_reason = override_reason.strip()
    row.overridden_by_user_id = user_id
    db.flush()
    return _serialize_ledger(row, include_finance=True)


def _serialize_ledger(row: BillingLedger, *, include_finance: bool) -> dict:
    case = row.case
    data = {
        "id": row.id,
        "caseId": row.case_id,
        "caseCode": case.case_code if case else "",
        "ledgerMonth": row.ledger_month,
        "eventDate": row.event_date.isoformat(),
        "eventType": row.event_type.value,
        "sourceType": row.source_type.value,
        "sourceId": row.source_id,
        "sessionId": row.session_id,
        "dailyLogId": row.daily_log_id,
        "billableStatus": row.billable_status.value,
        "quantity": float(row.quantity),
        "rateInr": float(row.rate_inr),
        "amountInr": float(row.amount_inr),
        "gstRatePercent": float(row.gst_rate_percent) if row.gst_rate_percent is not None else None,
        "gstAmountInr": float(row.gst_amount_inr) if row.gst_amount_inr is not None else None,
        "hsnSacCode": row.hsn_sac_code,
        "totalInr": float(row.total_inr),
        "clientInvoiceId": row.client_invoice_id,
        "adminNote": row.admin_note,
        "overrideReason": row.override_reason,
        "productBillingRuleId": row.product_billing_rule_id,
    }
    if include_finance:
        data["payoutAmountInr"] = float(row.payout_amount_inr) if row.payout_amount_inr is not None else None
        data["insighteMarginInr"] = float(row.insighte_margin_inr) if row.insighte_margin_inr is not None else None
    return data


def reconcile_month(db: Session, *, case_id: int, billing_month: str) -> dict:
    from sqlalchemy import extract, func

    ledger_rows = db.scalars(
        select(BillingLedger).where(
            BillingLedger.case_id == case_id,
            BillingLedger.ledger_month == billing_month,
        )
    ).all()
    client_billable = sum(
        float(r.total_inr)
        for r in ledger_rows
        if r.billable_status in (BillableStatus.BILLABLE, BillableStatus.INVOICED)
    )
    therapist_payout = 0.0
    engine_client = 0.0
    case = db.get(Case, case_id)
    if case:
        therapist_payout = payout_cycle.therapist_case_gross_inr(db, case, billing_month)
        engine_client = payout_cycle.client_case_gross_inr(db, case, billing_month)

    year_s, month_s = billing_month.split("-")[:2]
    session_count = db.scalar(
        select(func.count(TherapySession.id)).where(
            TherapySession.case_id == case_id,
            extract("year", TherapySession.scheduled_date) == int(year_s),
            extract("month", TherapySession.scheduled_date) == int(month_s),
            TherapySession.status == SessionStatus.COMPLETED,
        )
    ) or 0
    return {
        "caseId": case_id,
        "billingMonth": billing_month,
        "sessionCount": session_count,
        "ledgerBillableTotalInr": client_billable,
        "clientEngineTotalInr": engine_client,
        "therapistPayoutTotalInr": therapist_payout,
        "marginInr": round((client_billable or engine_client) - therapist_payout, 2),
        "ledgerRowCount": len(ledger_rows),
        "disputedRows": sum(1 for r in ledger_rows if r.dispute_status == LedgerDisputeStatus.OPEN),
    }


def ensure_period_charges(db: Session, *, case_id: int, billing_month: str) -> dict:
    if not _ledger_writes_allowed():
        return {"skipped": True, "reason": "BILLING_LEDGER_WRITES_disabled"}
    """Compute monthly/package period charges once per (case, month).

    Governing rule: always compute so finance can see it; billable only when the
    month has qualifying session evidence. Zero sessions → PENDING_FINANCE (DRAFT)
    until finance posts explicitly (or a future CRM prepaid start-of-service post).
    """
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    rule = _resolve_rule(db, case)
    session_count = count_qualifying_sessions_in_month(db, case_id=case_id, billing_month=billing_month)
    results: dict = {
        "caseId": case_id,
        "billingMonth": billing_month,
        "sessionCount": session_count,
        "monthlyFee": None,
        "packageCharge": None,
        "activeNoSessionsFlag": None,
    }

    if _case_is_monthly_fixed(case, rule) or (
        _uses_calendar_day_ledger(case) and not _case_is_package(case, rule)
    ):
        results["monthlyFee"] = _upsert_monthly_fee_charge(
            db, case=case, rule=rule, billing_month=billing_month, session_count=session_count
        )
    elif _case_is_package(case, rule):
        results["packageCharge"] = _upsert_package_purchase_charge(
            db, case=case, rule=rule, billing_month=billing_month, session_count=session_count
        )

    if _uses_calendar_day_ledger(case):
        _retire_uninvoiced_session_ledger(db, case_id=case_id, billing_month=billing_month)

    status = case.status if isinstance(case.status, CaseStatus) else CaseStatus(str(case.status))
    if session_count == 0 and status == CaseStatus.ACTIVE:
        results["activeNoSessionsFlag"] = _upsert_active_no_sessions_flag(
            db, case=case, billing_month=billing_month
        )
    elif session_count > 0:
        _resolve_active_no_sessions_flag(db, case_id=case_id, billing_month=billing_month)

    return results


def _retire_uninvoiced_session_ledger(db: Session, *, case_id: int, billing_month: str) -> int:
    """Calendar-day cases bill one period charge — do not also invoice session × rate rows."""
    rows = db.scalars(
        select(BillingLedger).where(
            BillingLedger.case_id == case_id,
            BillingLedger.ledger_month == billing_month,
            BillingLedger.source_type == LedgerSourceType.SESSION,
            BillingLedger.client_invoice_id.is_(None),
            BillingLedger.billable_status.in_(
                (
                    BillableStatus.BILLABLE,
                    BillableStatus.PENDING_REVIEW,
                    BillableStatus.PENDING_FINANCE,
                )
            ),
        )
    ).all()
    marker = "Superseded by calendar-day period charge"
    for row in rows:
        row.billable_status = BillableStatus.NON_BILLABLE
        note = (row.admin_note or "").strip()
        if marker not in note:
            row.admin_note = f"{note} {marker}".strip()
    if rows:
        db.flush()
    return len(rows)


def _backfill_approved_session_ledger(db: Session, *, case_id: int, billing_month: str) -> int:
    year_s, month_s = billing_month.split("-")[:2]
    logs = db.scalars(
        select(DailyLog)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            extract("year", TherapySession.scheduled_date) == int(year_s),
            extract("month", TherapySession.scheduled_date) == int(month_s),
            DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
        )
        .options(selectinload(DailyLog.session))
    ).all()
    synced = 0
    for log in logs:
        if upsert_from_daily_log_approved(db, log) is not None:
            synced += 1
    return synced


def sync_case_month_ledger(db: Session, *, case_id: int, billing_month: str) -> dict:
    """Create missing period charges and per-session rows so Build from ledger can run."""
    if not _ledger_writes_allowed():
        return {"skipped": True, "reason": "BILLING_LEDGER_WRITES_disabled"}
    period = ensure_period_charges(db, case_id=case_id, billing_month=billing_month)
    case = db.get(Case, case_id)
    rule = _resolve_rule(db, case) if case else None
    session_rows = 0
    if case and not _blocks_per_session_ledger(case, rule):
        session_rows = _backfill_approved_session_ledger(
            db, case_id=case_id, billing_month=billing_month
        )
    return {"skipped": False, "period": period, "sessionRowsSynced": session_rows}


def _period_billable_status(session_count: int) -> BillableStatus:
    if session_count > 0:
        return BillableStatus.BILLABLE
    return BillableStatus.PENDING_FINANCE


def _payout_cycle_client_amount(db: Session, case: Case, billing_month: str) -> tuple[float, str]:
    amount = payout_cycle.client_case_gross_inr(db, case, billing_month)
    segs = payout_cycle.build_cycle_segments(db, case, billing_month)
    if payout_cycle.uses_calendar_day_pay(case):
        units = sum(max(s.calendar_days - s.unpaid_leaves, 0) for s in segs)
        kind = "calendar-days"
    else:
        units = sum(s.approved_sessions for s in segs)
        kind = "approved-sessions"
    note = (
        f"{len(segs)} therapist segment(s), {units} {kind}, client allotment ₹{amount}"
    )
    return amount, note


def _upsert_monthly_fee_charge(
    db: Session,
    *,
    case: Case,
    rule: ProductBillingRule | None,
    billing_month: str,
    session_count: int,
) -> dict:
    _, month_end = _month_bounds(billing_month)
    amount, breakdown = _payout_cycle_client_amount(db, case, billing_month)
    rate = payout_cycle.client_configured_share_inr(case)
    if rate <= 0:
        rate = float(case.client_monthly_rate_inr or case.package_amount_inr or 0)
    amount, gst_rate, gst_amount, hsn = _amounts(amount, rule)
    total = round(amount + (gst_amount or 0), 2)
    status = _period_billable_status(session_count)
    note = f"MONTHLY_FIXED payout-cycle. {breakdown}"

    existing = _existing_period_charge(
        db,
        source_type=LedgerSourceType.MONTHLY_FEE,
        case_id=case.id,
        ledger_month=billing_month,
    )
    parent_id = _parent_for_case(db, case)
    if existing:
        if _ledger_amounts_frozen(existing.billable_status):
            return _serialize_ledger(existing, include_finance=True)
        # Do not silently demote a finance-posted BILLABLE row back to PENDING_FINANCE
        # when re-running with zero sessions later — keep BILLABLE if already posted.
        if existing.billable_status == BillableStatus.BILLABLE and session_count == 0:
            status = BillableStatus.BILLABLE
        existing.event_type = LedgerEventType.MONTHLY_FEE
        existing.billable_status = status
        existing.rate_inr = rate
        existing.amount_inr = amount
        existing.gst_rate_percent = gst_rate
        existing.gst_amount_inr = gst_amount
        existing.hsn_sac_code = hsn
        existing.total_inr = total
        existing.quantity = 1
        existing.admin_note = note
        existing.product_billing_rule_id = rule.id if rule else existing.product_billing_rule_id
        existing.parent_user_id = parent_id
        existing.event_date = month_end
        db.flush()
        return _serialize_ledger(existing, include_finance=True)

    row = BillingLedger(
        case_id=case.id,
        parent_user_id=parent_id,
        therapist_user_id=None,
        product_billing_rule_id=rule.id if rule else None,
        source_type=LedgerSourceType.MONTHLY_FEE,
        source_id=case.id,
        session_id=None,
        daily_log_id=None,
        ledger_month=billing_month,
        event_date=month_end,
        event_type=LedgerEventType.MONTHLY_FEE,
        billable_status=status,
        quantity=1,
        rate_inr=rate,
        amount_inr=amount,
        gst_rate_percent=gst_rate,
        gst_amount_inr=gst_amount,
        hsn_sac_code=hsn,
        total_inr=total,
        admin_note=note,
        dispute_status=LedgerDisputeStatus.NONE,
    )
    db.add(row)
    db.flush()
    return _serialize_ledger(row, include_finance=True)


def _upsert_package_purchase_charge(
    db: Session,
    *,
    case: Case,
    rule: ProductBillingRule | None,
    billing_month: str,
    session_count: int,
) -> dict:
    """One package charge from the payout-cycle client allotment (not a silent full lump)."""
    amount, breakdown = _payout_cycle_client_amount(db, case, billing_month)
    rate = amount if amount else float(case.package_amount_inr or 0)
    amount, gst_rate, gst_amount, hsn = _amounts(amount, rule)
    total = round(amount + (gst_amount or 0), 2)
    status = _period_billable_status(session_count)
    _, month_end = _month_bounds(billing_month)
    note = f"PACKAGE_PURCHASE payout-cycle. {breakdown}"

    existing = _existing_period_charge(
        db,
        source_type=LedgerSourceType.PACKAGE_PURCHASE,
        case_id=case.id,
        ledger_month=billing_month,
    )
    parent_id = _parent_for_case(db, case)
    if existing:
        if _ledger_amounts_frozen(existing.billable_status):
            return _serialize_ledger(existing, include_finance=True)
        if existing.billable_status == BillableStatus.BILLABLE and session_count == 0:
            status = BillableStatus.BILLABLE
        existing.event_type = LedgerEventType.MANUAL_ADJUSTMENT
        existing.billable_status = status
        existing.rate_inr = rate
        existing.amount_inr = amount
        existing.gst_rate_percent = gst_rate
        existing.gst_amount_inr = gst_amount
        existing.hsn_sac_code = hsn
        existing.total_inr = total
        existing.quantity = 1
        existing.admin_note = note
        existing.product_billing_rule_id = rule.id if rule else existing.product_billing_rule_id
        existing.parent_user_id = parent_id
        existing.event_date = month_end
        db.flush()
        return _serialize_ledger(existing, include_finance=True)

    # PACKAGE_PURCHASE has no dedicated LedgerEventType — use MANUAL_ADJUSTMENT label
    # on a PACKAGE_PURCHASE source row (source_type is the idempotent key).
    row = BillingLedger(
        case_id=case.id,
        parent_user_id=parent_id,
        therapist_user_id=None,
        product_billing_rule_id=rule.id if rule else None,
        source_type=LedgerSourceType.PACKAGE_PURCHASE,
        source_id=case.id,
        session_id=None,
        daily_log_id=None,
        ledger_month=billing_month,
        event_date=month_end,
        event_type=LedgerEventType.MANUAL_ADJUSTMENT,
        billable_status=status,
        quantity=1,
        rate_inr=rate,
        amount_inr=amount,
        gst_rate_percent=gst_rate,
        gst_amount_inr=gst_amount,
        hsn_sac_code=hsn,
        total_inr=total,
        admin_note=note,
        dispute_status=LedgerDisputeStatus.NONE,
    )
    db.add(row)
    db.flush()
    return _serialize_ledger(row, include_finance=True)


def _upsert_active_no_sessions_flag(db: Session, *, case: Case, billing_month: str) -> dict:
    existing = db.scalars(
        select(BillingPeriodFlag).where(
            BillingPeriodFlag.case_id == case.id,
            BillingPeriodFlag.ledger_month == billing_month,
            BillingPeriodFlag.flag_kind == PeriodFlagKind.ACTIVE_NO_SESSIONS,
        )
    ).first()
    status_val = case.status.value if hasattr(case.status, "value") else str(case.status)
    message = "client active, no sessions done"
    if existing:
        existing.case_status = status_val
        existing.session_count = 0
        existing.message = message
        existing.resolved = False
        db.flush()
        return _serialize_period_flag(existing)
    flag = BillingPeriodFlag(
        case_id=case.id,
        ledger_month=billing_month,
        flag_kind=PeriodFlagKind.ACTIVE_NO_SESSIONS,
        case_status=status_val,
        session_count=0,
        message=message,
        resolved=False,
    )
    db.add(flag)
    db.flush()
    return _serialize_period_flag(flag)


def _resolve_active_no_sessions_flag(db: Session, *, case_id: int, billing_month: str) -> None:
    existing = db.scalars(
        select(BillingPeriodFlag).where(
            BillingPeriodFlag.case_id == case_id,
            BillingPeriodFlag.ledger_month == billing_month,
            BillingPeriodFlag.flag_kind == PeriodFlagKind.ACTIVE_NO_SESSIONS,
            BillingPeriodFlag.resolved.is_(False),
        )
    ).first()
    if existing:
        existing.resolved = True
        db.flush()


def _serialize_period_flag(flag: BillingPeriodFlag) -> dict:
    return {
        "id": flag.id,
        "caseId": flag.case_id,
        "ledgerMonth": flag.ledger_month,
        "flagKind": flag.flag_kind.value,
        "caseStatus": flag.case_status,
        "sessionCount": flag.session_count,
        "message": flag.message,
        "resolved": flag.resolved,
    }


def list_period_flags(
    db: Session,
    *,
    ledger_month: Optional[str] = None,
    case_id: Optional[int] = None,
    unresolved_only: bool = True,
) -> list[dict]:
    stmt = select(BillingPeriodFlag).order_by(BillingPeriodFlag.ledger_month.desc(), BillingPeriodFlag.id.desc())
    if ledger_month:
        stmt = stmt.where(BillingPeriodFlag.ledger_month == ledger_month)
    if case_id:
        stmt = stmt.where(BillingPeriodFlag.case_id == case_id)
    if unresolved_only:
        stmt = stmt.where(BillingPeriodFlag.resolved.is_(False))
    return [_serialize_period_flag(f) for f in db.scalars(stmt.limit(500)).all()]


def post_pending_finance_charge(db: Session, ledger_id: int, *, user_id: int, note: str | None = None) -> dict:
    """Explicit finance action: PENDING_FINANCE → BILLABLE."""
    if not _ledger_writes_allowed():
        raise ValueError("Posting disabled until ledger writes are enabled (pre-cutover).")
    row = db.get(BillingLedger, ledger_id)
    if not row:
        raise ValueError("Ledger row not found")
    if row.billable_status != BillableStatus.PENDING_FINANCE:
        raise ValueError("Only PENDING_FINANCE charges can be posted by finance")
    if row.source_type not in (LedgerSourceType.MONTHLY_FEE, LedgerSourceType.PACKAGE_PURCHASE):
        raise ValueError("Only monthly/package period charges can be posted this way")
    row.billable_status = BillableStatus.BILLABLE
    row.overridden_by_user_id = user_id
    row.override_reason = (note or "Posted by finance from draft / pending finance").strip()
    db.flush()
    return _serialize_ledger(row, include_finance=True)


def consume_package_session(db: Session, *, case_id: int, session: TherapySession) -> BillingLedger | None:
    if not _ledger_writes_allowed():
        return None
    from app.models.client_billing import CarePackage, CarePackageStatus

    # Idempotency guard — do not double-consume for the same session.
    existing_consumption = db.scalars(
        select(BillingLedger).where(
            BillingLedger.source_type == LedgerSourceType.PACKAGE_CONSUMPTION,
            BillingLedger.session_id == session.id,
        )
    ).first()
    if existing_consumption:
        return existing_consumption

    pkg = db.scalars(
        select(CarePackage)
        .where(
            CarePackage.case_id == case_id,
            CarePackage.status == CarePackageStatus.ACTIVE,
        )
        .order_by(CarePackage.id.desc())
    ).first()
    if not pkg or pkg.used_sessions >= pkg.total_sessions:
        return None
    pkg.used_sessions += 1
    if pkg.used_sessions >= pkg.total_sessions:
        pkg.status = CarePackageStatus.EXHAUSTED
    case = db.get(Case, case_id)
    rule = _resolve_rule(db, case) if case else None
    row = BillingLedger(
        case_id=case_id,
        parent_user_id=pkg.parent_user_id,
        therapist_user_id=session.therapist_user_id,
        product_billing_rule_id=pkg.product_billing_rule_id or (rule.id if rule else None),
        source_type=LedgerSourceType.PACKAGE_CONSUMPTION,
        source_id=session.id,
        session_id=session.id,
        care_package_id=pkg.id,
        ledger_month=_ledger_month(session.scheduled_date),
        event_date=session.scheduled_date,
        event_type=LedgerEventType.PACKAGE_CONSUMPTION,
        billable_status=BillableStatus.BILLABLE,
        quantity=1,
        rate_inr=0,
        amount_inr=0,
        total_inr=0,
    )
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------------------
# Central financial effect resolver
# ---------------------------------------------------------------------------

# Individual / per-session product categories where child absence = cancelled/not billable.
_PER_SESSION_CATEGORIES = frozenset(
    {
        "homecare",
        "counselling",
        "special_educator",
        "behavior_therapy",
        "play_therapy",
        "occupational_therapy",
        "speech_therapy",
        "assessment",
        "parent_training",
        "other",
        "other_clinical",
    }
)


@dataclass
class FinancialEffect:
    client_billable: bool
    package_consumed: bool
    therapist_payable: bool
    therapist_deductible: bool
    ledger_event_type: LedgerEventType
    report_label: str


def resolve_session_financial_effect(
    outcome: SessionStatus,
    case: Case,
    rule: Optional[ProductBillingRule],
) -> FinancialEffect:
    """Return the financial effect of a session attendance outcome.

    Routes based on billing_model + product_category from the matched ProductBillingRule.
    Falls back to per-session (non-billable) behaviour when no rule is found.
    """
    billing_model = rule.billing_model if rule else None
    product_category = (rule.product_category if rule else None) or (
        getattr(case, "product_module", None) or "unknown"
    )
    product_category = product_category.strip().lower()

    # --- CHILD_ABSENT / CLIENT_ABSENT / NO_SHOW ---
    if outcome in (SessionStatus.CLIENT_ABSENT, SessionStatus.NO_SHOW):
        is_package_or_retainer = (
            billing_model in (ProductBillingModel.PREPAID_PACKAGE, ProductBillingModel.MONTHLY_FIXED)
            or product_category in ("shadow_support", "school_support", "school_services")
        )
        if is_package_or_retainer:
            return FinancialEffect(
                client_billable=False,
                package_consumed=bool(rule and getattr(rule, "package_consumes_on_child_absent", False)),
                therapist_payable=bool(rule and getattr(rule, "child_absent_therapist_payable", False)),
                therapist_deductible=False,
                ledger_event_type=LedgerEventType.CHILD_ABSENT,
                report_label="Child absent",
            )
        # Per-session individual services
        return FinancialEffect(
            client_billable=bool(rule and rule.client_no_show_billable),
            package_consumed=False,
            therapist_payable=False,
            therapist_deductible=False,
            ledger_event_type=LedgerEventType.CLIENT_NO_SHOW,
            report_label="Child absent — session not delivered",
        )

    # --- THERAPIST_LEAVE ---
    if outcome == SessionStatus.THERAPIST_LEAVE:
        is_shadow = product_category in ("shadow_support", "school_support")
        therapist_payable = False
        therapist_deductible = False
        if is_shadow and rule and rule.included_paid_leaves:
            # Leave policy configured: mark as payable; full balance check in payout service.
            therapist_payable = True
            therapist_deductible = False
        elif is_shadow:
            therapist_payable = False
            therapist_deductible = bool(rule and rule.unpaid_leave_deduction_method)
        return FinancialEffect(
            client_billable=False,
            package_consumed=False,
            therapist_payable=therapist_payable,
            therapist_deductible=therapist_deductible,
            ledger_event_type=LedgerEventType.THERAPIST_CANCEL,
            report_label="Therapist leave",
        )

    # --- CANCELLED ---
    if outcome == SessionStatus.CANCELLED:
        return FinancialEffect(
            client_billable=False,
            package_consumed=False,
            therapist_payable=False,
            therapist_deductible=False,
            ledger_event_type=LedgerEventType.SESSION_CANCELLED,
            report_label="Session cancelled",
        )

    # Default fallback
    logger.warning("resolve_session_financial_effect: unhandled outcome %s for case %s", outcome, case.id)
    return FinancialEffect(
        client_billable=False,
        package_consumed=False,
        therapist_payable=False,
        therapist_deductible=False,
        ledger_event_type=LedgerEventType.SESSION_CANCELLED,
        report_label=str(outcome),
    )
