"""Step 6 — assignment windows, leave precedence, rate changes, package status-once, add-ons.

Staging calculation helpers. Does not invent hourly proration. Client vs therapist money stay separate.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.billing_step6 import (
    AddOnKind,
    BillingCalcException,
    BillingCalcExceptionCode,
    CaseClientRatePeriod,
    EffectiveDateChoice,
)
from app.models.case import BillingType, Case, CompensationMode
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.ledger_billing import ProductBillingRule
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceType
from app.models.user import User
from app.core.billing_validation import resolve_therapist_pay
from app.services.billing_ledger_service import (
    EffectiveRatePeriod,
    _MONTHLY_PRORATION_DAYS,
    _inclusive_days,
    _month_bounds,
)
from app.services import leave_policy_service

# ---------------------------------------------------------------------------
# Add-on legacy mapping (read path — never rewrites ledger history)
# ---------------------------------------------------------------------------


def effective_add_on_kind(session: TherapySession) -> AddOnKind | None:
    """Prefer explicit add_on_kind; legacy is_additional_visit → EXTRA_DAY without mutating money."""
    raw = (getattr(session, "add_on_kind", None) or "").strip()
    if raw:
        try:
            return AddOnKind(raw)
        except ValueError:
            return None
    if getattr(session, "is_additional_visit", False):
        return AddOnKind.EXTRA_DAY
    return None


# ---------------------------------------------------------------------------
# Inclusive assignment / rate windows
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InclusiveWindow:
    start: date
    end: date  # inclusive; open-ended clipped to month_end by callers
    label: str = ""
    meta: dict = field(default_factory=dict)


def clip_inclusive(window_start: date, window_end: date | None, month_start: date, month_end: date) -> tuple[date, date] | None:
    """Inclusive start/end. null end_date = open-ended. Adjacent A ends 14 / B starts 15 is NOT a gap."""
    end = window_end if window_end is not None else month_end
    start = max(window_start, month_start)
    end = min(end, month_end)
    if start > end:
        return None
    return start, end


def assignment_windows_for_month(
    db: Session,
    *,
    case_id: int,
    month_start: date,
    month_end: date,
) -> tuple[list[InclusiveWindow], list[dict]]:
    """Active assignment slices in month. Overlaps → ASSIGNMENT_PERIOD_OVERLAP exception."""
    rows = db.scalars(
        select(CaseAssignment)
        .where(CaseAssignment.case_id == case_id)
        .order_by(CaseAssignment.start_date, CaseAssignment.id)
    ).all()
    windows: list[InclusiveWindow] = []
    exceptions: list[dict] = []
    for a in rows:
        if a.status not in (CaseAssignmentStatus.ACTIVE, CaseAssignmentStatus.ENDED, CaseAssignmentStatus.TRANSFERRED):
            continue
        clipped = clip_inclusive(a.start_date, a.end_date, month_start, month_end)
        if not clipped:
            continue
        windows.append(
            InclusiveWindow(
                clipped[0],
                clipped[1],
                label=f"assignment:{a.id}",
                meta={"assignment_id": a.id, "therapist_user_id": a.therapist_user_id},
            )
        )
    # Overlap check (adjacent boundaries OK: end==next.start-1)
    for i in range(len(windows)):
        for j in range(i + 1, len(windows)):
            a, b = windows[i], windows[j]
            if a.start <= b.end and b.start <= a.end:
                exceptions.append(
                    {
                        "code": BillingCalcExceptionCode.ASSIGNMENT_PERIOD_OVERLAP.value,
                        "message": f"Assignment windows overlap {a.start}–{a.end} and {b.start}–{b.end}",
                    }
                )
    if not windows:
        # Legacy fallback: whole month (case still billable without assignment history gaps)
        windows = [InclusiveWindow(month_start, month_end, label="legacy_full_month")]
    return windows, exceptions


# ---------------------------------------------------------------------------
# Client rate periods (legacy: no history rows = current case rate is valid)
# ---------------------------------------------------------------------------


def client_rate_periods_for_month(
    db: Session,
    case: Case,
    *,
    month_start: date,
    month_end: date,
) -> tuple[list[EffectiveRatePeriod], list[dict]]:
    """
    Build client billing rate periods for the month.
    No history table rows → single current rate baseline (not an exception).
    Retainer overrides client rate only (never therapist payout).
    """
    exceptions: list[dict] = []
    history = db.scalars(
        select(CaseClientRatePeriod)
        .where(CaseClientRatePeriod.case_id == case.id)
        .order_by(CaseClientRatePeriod.start_date, CaseClientRatePeriod.id)
    ).all()

    base_rate = float(case.client_monthly_rate_inr or 0)
    periods: list[EffectiveRatePeriod] = []

    if not history:
        # Valid legacy baseline — ADD 7
        assign_wins, assign_ex = assignment_windows_for_month(
            db, case_id=case.id, month_start=month_start, month_end=month_end
        )
        exceptions.extend(assign_ex)
        for w in assign_wins:
            periods.append(EffectiveRatePeriod(w.start, w.end, base_rate, "normal"))
    else:
        # Detect unresolved change dates
        for h in history:
            if h.effective_date_choice and not h.resolved_effective_date and not h.start_date:
                exceptions.append(
                    {
                        "code": BillingCalcExceptionCode.RATE_CHANGE_DATE_UNRESOLVED.value,
                        "message": f"Rate period {h.id} has no resolved effective date",
                    }
                )
        # Sort and clip; detect gaps/overlaps within month
        clipped: list[tuple[date, date, float, str]] = []
        for h in history:
            c = clip_inclusive(h.start_date, h.end_date, month_start, month_end)
            if not c:
                continue
            clipped.append((c[0], c[1], float(h.rate_inr), h.label or "normal"))
        clipped.sort(key=lambda x: x[0])
        for i in range(len(clipped)):
            for j in range(i + 1, len(clipped)):
                a, b = clipped[i], clipped[j]
                if a[0] <= b[1] and b[0] <= a[1]:
                    exceptions.append(
                        {
                            "code": BillingCalcExceptionCode.RATE_PERIOD_OVERLAP.value,
                            "message": f"Rate periods overlap {a[0]}–{a[1]} and {b[0]}–{b[1]}",
                        }
                    )
        for i in range(len(clipped) - 1):
            a, b = clipped[i], clipped[i + 1]
            # Adjacent (a.end+1 == b.start) is fine; gap if a.end+1 < b.start
            if a[1] + timedelta(days=1) < b[0]:
                exceptions.append(
                    {
                        "code": BillingCalcExceptionCode.RATE_PERIOD_GAP.value,
                        "message": f"Rate period gap between {a[1]} and {b[0]}",
                    }
                )
        for start, end, rate, label in clipped:
            periods.append(EffectiveRatePeriod(start, end, rate, label))
        if not periods:
            periods = [EffectiveRatePeriod(month_start, month_end, base_rate, "normal")]

    # Retainer overlays client rate only (ADD 6)
    periods = _apply_client_retainer_overlay(case, periods, month_start, month_end)
    return periods, exceptions


def _apply_client_retainer_overlay(
    case: Case,
    periods: list[EffectiveRatePeriod],
    month_start: date,
    month_end: date,
) -> list[EffectiveRatePeriod]:
    ret_rate = float(case.retainer_rate_inr) if case.retainer_rate_inr is not None else None
    ret_start, ret_end = case.retainer_start_date, case.retainer_end_date
    if ret_rate is None or ret_rate <= 0 or not ret_start or not ret_end:
        return periods
    out: list[EffectiveRatePeriod] = []
    for p in periods:
        r0 = max(p.start, ret_start)
        r1 = min(p.end, ret_end)
        if r0 <= r1:
            if p.start < r0:
                out.append(EffectiveRatePeriod(p.start, r0 - timedelta(days=1), p.rate_inr, p.label))
            out.append(EffectiveRatePeriod(r0, r1, ret_rate, "retainer"))
            if r1 < p.end:
                out.append(EffectiveRatePeriod(r1 + timedelta(days=1), p.end, p.rate_inr, p.label))
        else:
            out.append(p)
    return [x for x in out if _inclusive_days(x.start, x.end) > 0]


# ---------------------------------------------------------------------------
# Leave precedence (FIX 4)
# ---------------------------------------------------------------------------


@dataclass
class LeaveDayDecision:
    day: date
    deductible: bool
    reason: str
    exception_code: str | None = None


def classify_leave_day(
    *,
    leave_type: LeaveType | str | None,
    billing_category: LeaveBillingCategory | str | None,
    absence_type: SessionAbsenceType | str | None,
    sick_credit_available: bool | None,
    credit_system_exists: bool,
) -> LeaveDayDecision:
    """
    Ladder:
    1. CHILD_ABSENCE / SCHOOL_HOLIDAY → never deducted
    2. PAID_LEAVE → never deducted
    3. SICK_LEAVE → credit if available else deduct; missing balance → exception
    4. UNPAID_LEAVE → always deduct
    5. Unknown → exception
    """
    # Placeholder day filled by caller
    day = date.min
    at = absence_type.value if isinstance(absence_type, SessionAbsenceType) else (absence_type or "")
    at_u = str(at).upper()
    if at_u in ("CLIENT_ABSENT", "CHILD_ABSENT", "CHILD_ABSENCE", "SCHOOL_HOLIDAY", "NO_SHOW"):
        return LeaveDayDecision(day, False, "child_absence_or_holiday_never_deducted")

    lt = leave_type.value if isinstance(leave_type, LeaveType) else (leave_type or "")
    lt_u = str(lt).upper()
    cat = billing_category.value if isinstance(billing_category, LeaveBillingCategory) else (billing_category or "")
    cat_u = str(cat).upper()

    if cat_u == "PAID" or lt_u in ("ANNUAL", "CASUAL", "PAID_LEAVE"):
        return LeaveDayDecision(day, False, "paid_leave_never_deducted")

    if lt_u in ("SICK", "SICK_LEAVE"):
        if credit_system_exists and sick_credit_available is None:
            return LeaveDayDecision(
                day,
                False,
                "missing_leave_credit_balance",
                BillingCalcExceptionCode.MISSING_LEAVE_CREDIT_BALANCE.value,
            )
        if credit_system_exists and sick_credit_available:
            return LeaveDayDecision(day, False, "sick_consumed_credit")
        # No credit system at all → sick is deductible (FIX 4)
        return LeaveDayDecision(day, True, "sick_no_credit_deduct")

    if cat_u == "UNPAID" or lt_u in ("UNPAID", "UNPAID_LEAVE"):
        return LeaveDayDecision(day, True, "unpaid_always_deduct")

    if not lt_u and not cat_u and not at_u:
        return LeaveDayDecision(
            day,
            False,
            "unknown_leave_type",
            BillingCalcExceptionCode.UNKNOWN_LEAVE_TYPE.value,
        )

    return LeaveDayDecision(
        day,
        False,
        "unknown_leave_type",
        BillingCalcExceptionCode.UNKNOWN_LEAVE_TYPE.value,
    )


def deductible_leave_dates_for_month(
    db: Session,
    *,
    case: Case,
    therapist_user_id: int | None,
    month_start: date,
    month_end: date,
) -> tuple[set[date], list[dict]]:
    """Collect deductible leave dates in month using the precedence ladder."""
    exceptions: list[dict] = []
    deductible: set[date] = set()
    credit_system_exists = True  # leave_policy_service exists in this codebase
    sick_credit_available: bool | None = None

    if therapist_user_id:
        user = db.get(User, therapist_user_id)
        if user:
            bal = leave_policy_service.get_leave_balance(db, user, year=month_start.year)
            if bal.get("requires_employment_start_date") or not bal.get("balance_updated"):
                sick_credit_available = None
            else:
                sick_credit_available = int(bal.get("leave_credit_pending") or 0) > 0

    leaves = []
    if therapist_user_id:
        leaves = db.scalars(
            select(TherapistLeave).where(
                TherapistLeave.therapist_user_id == therapist_user_id,
                TherapistLeave.status == LeaveStatus.APPROVED,
                TherapistLeave.start_date <= month_end,
                TherapistLeave.end_date >= month_start,
            )
        ).all()

    remaining_sick_credits = None
    if sick_credit_available is True and therapist_user_id:
        user = db.get(User, therapist_user_id)
        if user:
            remaining_sick_credits = int(
                leave_policy_service.get_leave_balance(db, user, year=month_start.year).get(
                    "leave_credit_pending"
                )
                or 0
            )

    for leave in leaves:
        # Scope: case-specific leave or global therapist leave
        case_ids = []
        if leave.case_ids:
            case_ids = [int(x) for x in leave.case_ids if x is not None]
        elif leave.case_id is not None:
            case_ids = [int(leave.case_id)]
        if case_ids and case.id not in case_ids:
            continue

        d0 = max(leave.start_date, month_start)
        d1 = min(leave.end_date, month_end)
        day = d0
        while day <= d1:
            credit_ok = None
            if leave.leave_type == LeaveType.SICK:
                if remaining_sick_credits is None and sick_credit_available is None:
                    credit_ok = None
                elif remaining_sick_credits is not None:
                    credit_ok = remaining_sick_credits > 0
                else:
                    credit_ok = bool(sick_credit_available)

            decision = classify_leave_day(
                leave_type=leave.leave_type,
                billing_category=leave.billing_category,
                absence_type=None,
                sick_credit_available=credit_ok,
                credit_system_exists=credit_system_exists,
            )
            decision.day = day
            if decision.exception_code:
                exceptions.append(
                    {
                        "code": decision.exception_code,
                        "message": f"{decision.reason} on {day.isoformat()}",
                    }
                )
            elif decision.deductible:
                deductible.add(day)
            elif decision.reason == "sick_consumed_credit" and remaining_sick_credits is not None:
                remaining_sick_credits = max(remaining_sick_credits - 1, 0)
            day += timedelta(days=1)

    return deductible, exceptions


# ---------------------------------------------------------------------------
# FIX 1 — monthly client amount
# ---------------------------------------------------------------------------


def compute_monthly_fixed_amount_v6(
    periods: list[EffectiveRatePeriod],
    *,
    month_start: date,
    month_end: date,
    deductible_leave_dates: Iterable[date] | None = None,
) -> tuple[float, int, str]:
    """
    Full uninterrupted eligible month → flat monthly rate (never rate/30 × calendar_days).
    Each deductible leave day deducts rate/30 from that flat (same-rate months).
    Remaining allocated across sub-periods by eligible calendar days.
    Multi-rate (retainer): sum (rate_i/30)*eligible_days_i with leave days removed from periods.
    """
    if not periods:
        return 0.0, 0, ""

    leave_set = {d for d in (deductible_leave_dates or []) if month_start <= d <= month_end}

    def eligible_days(p: EffectiveRatePeriod) -> int:
        days = 0
        d = p.start
        while d <= p.end:
            if d not in leave_set:
                days += 1
            d += timedelta(days=1)
        return days

    rates = {p.rate_inr for p in periods}
    single_rate = len(rates) == 1
    rate = next(iter(rates)) if single_rate else None

    covers_full = (
        min(p.start for p in periods) == month_start
        and max(p.end for p in periods) == month_end
        and _period_union_covers(periods, month_start, month_end)
    )

    if single_rate and rate is not None and covers_full and not leave_set:
        return round(rate, 2), _MONTHLY_PRORATION_DAYS, f"full-month flat @₹{rate}/mo"

    if single_rate and rate is not None:
        leave_deduction = round((rate / _MONTHLY_PRORATION_DAYS) * len(leave_set), 2)
        net = round(rate - leave_deduction, 2)
        elig = [(p, eligible_days(p)) for p in periods]
        total_elig = sum(e for _, e in elig)
        if total_elig <= 0:
            return 0.0, 0, f"all days leave-deducted; leave={len(leave_set)}×₹{rate}/30"
        amount = 0.0
        bits = []
        for p, ed in elig:
            if ed <= 0:
                continue
            part = round(net * (ed / total_elig), 2)
            amount += part
            bits.append(f"{p.label}:{ed}d→₹{part}")
        # Fix residual rounding so parts sum to net
        amount = round(amount, 2)
        if abs(amount - net) <= 0.05:
            amount = net
        note = f"flat ₹{rate} − {len(leave_set)}×₹{rate}/30=₹{leave_deduction}; alloc {'; '.join(bits)}"
        return amount, min(total_elig, _MONTHLY_PRORATION_DAYS), note

    # Multi-rate (retainer): per-period /30 × eligible days; leave removed from day counts
    amount = 0.0
    billed = 0
    bits = []
    for p in periods:
        ed = eligible_days(p)
        if ed <= 0:
            continue
        part = round((p.rate_inr / _MONTHLY_PRORATION_DAYS) * ed, 2)
        amount += part
        billed += ed
        bits.append(f"{p.label}:{ed}d@₹{p.rate_inr}/mo=₹{part}")
    return round(amount, 2), billed, "; ".join(bits)


def _period_union_covers(periods: list[EffectiveRatePeriod], month_start: date, month_end: date) -> bool:
    days = set()
    for p in periods:
        d = p.start
        while d <= p.end:
            days.add(d)
            d += timedelta(days=1)
    expected = (month_end - month_start).days + 1
    return len(days) >= expected


# ---------------------------------------------------------------------------
# Package status-once (FIX 2 + FIX 3)
# ---------------------------------------------------------------------------


@dataclass
class PackageUnitEffect:
    client_package_charge_reduced: bool
    therapist_payable: bool
    package_consumed: bool
    reschedulable: bool
    reason: str


def package_unit_effect_for_status(
    status: SessionStatus | str,
    *,
    rule: ProductBillingRule | None,
    is_add_on_beyond_package: bool = False,
) -> PackageUnitEffect:
    st = status.value if isinstance(status, SessionStatus) else str(status)
    if is_add_on_beyond_package:
        return PackageUnitEffect(False, True, False, False, "add_on_beyond_package")
    if st == SessionStatus.COMPLETED.value:
        return PackageUnitEffect(False, True, True, False, "delivered")
    if st in (SessionStatus.CLIENT_ABSENT.value, SessionStatus.NO_SHOW.value):
        payable = bool(rule and getattr(rule, "child_absent_therapist_payable", False))
        consume = bool(rule and getattr(rule, "package_consumes_on_child_absent", False))
        return PackageUnitEffect(False, payable, consume, not consume, "child_absent_policy")
    if st == SessionStatus.THERAPIST_LEAVE.value:
        # Not payable — session didn't happen. Do NOT payable-then-deduct.
        return PackageUnitEffect(False, False, False, True, "therapist_leave_not_payable")
    return PackageUnitEffect(False, False, False, False, f"status_{st}")


def therapist_package_payout_amount(
    case: Case,
    *,
    payable_units: int,
    db: Session | None = None,
    as_of: date | None = None,
) -> float:
    """FIX 2: never use client package_amount_inr for therapist payout.

    Missing package_session_count is an exception — never guess `or 1`.
    """
    if not case.package_session_count or int(case.package_session_count) <= 0:
        raise ValueError(BillingCalcExceptionCode.MISSING_PACKAGE_COUNT.value)
    pkg_count = int(case.package_session_count)
    if db is not None and as_of is not None:
        from app.services import billing_rate_history_service

        base = billing_rate_history_service.resolve_therapist_pay_as_of(db, case, as_of)
    else:
        base = resolve_therapist_pay(case)
    return round((base / pkg_count) * payable_units, 2)


# ---------------------------------------------------------------------------
# Rate-change effective date resolution
# ---------------------------------------------------------------------------


def resolve_effective_date(
    db: Session,
    *,
    case_id: int,
    choice: EffectiveDateChoice | str,
    change_date: date | None,
    approval_at: datetime | None,
    billing_month: str,
) -> tuple[date | None, str | None]:
    """
    START_OF_MONTH → first calendar date of billing month.
    CHANGE_DATE → user-entered change date.
    NEXT_SESSION_ONWARD → first eligible completed session on/after approval; else defer.
    """
    month_start, month_end = _month_bounds(billing_month)
    ch = choice.value if isinstance(choice, EffectiveDateChoice) else str(choice)
    if ch == EffectiveDateChoice.START_OF_MONTH.value:
        return month_start, None
    if ch == EffectiveDateChoice.CHANGE_DATE.value:
        if not change_date:
            return None, BillingCalcExceptionCode.RATE_CHANGE_DATE_UNRESOLVED.value
        return change_date, None
    if ch == EffectiveDateChoice.NEXT_SESSION_ONWARD.value:
        if not approval_at:
            return None, BillingCalcExceptionCode.RATE_CHANGE_DATE_UNRESOLVED.value
        anchor = approval_at.date() if isinstance(approval_at, datetime) else approval_at
        sess = db.scalars(
            select(TherapySession)
            .where(
                TherapySession.case_id == case_id,
                TherapySession.status == SessionStatus.COMPLETED,
                TherapySession.scheduled_date >= anchor,
                TherapySession.actual_start_at.isnot(None),
                TherapySession.actual_end_at.isnot(None),
            )
            .order_by(TherapySession.scheduled_date, TherapySession.id)
            .limit(1)
        ).first()
        if sess:
            return sess.scheduled_date, None
        # No eligible session this month → keep previous rate; new rate waits for later month
        return None, None
    return None, BillingCalcExceptionCode.RATE_CHANGE_DATE_UNRESOLVED.value


def apply_client_rate_change(
    db: Session,
    *,
    case: Case,
    new_rate_inr: float,
    choice: EffectiveDateChoice | str,
    change_date: date | None,
    approval_at: datetime | None,
    billing_month: str,
    actor_user_id: int | None,
) -> CaseClientRatePeriod:
    """Record mid-month client rate change with choice + resolved date for audit."""
    resolved, err = resolve_effective_date(
        db,
        case_id=case.id,
        choice=choice,
        change_date=change_date,
        approval_at=approval_at,
        billing_month=billing_month,
    )
    if err == BillingCalcExceptionCode.RATE_CHANGE_DATE_UNRESOLVED.value:
        raise ValueError("Rate change date could not be resolved — pick a date or wait for a session")
    month_start, _ = _month_bounds(billing_month)
    start = resolved or month_start
    # Close prior open-ended period the day before
    open_rows = db.scalars(
        select(CaseClientRatePeriod).where(
            CaseClientRatePeriod.case_id == case.id,
            CaseClientRatePeriod.end_date.is_(None),
        )
    ).all()
    for row in open_rows:
        if row.start_date < start:
            row.end_date = start - timedelta(days=1)
        elif row.start_date >= start:
            row.end_date = row.start_date  # zero-length; cleaned by overlap checks
    period = CaseClientRatePeriod(
        case_id=case.id,
        start_date=start,
        end_date=None,
        rate_inr=new_rate_inr,
        label="normal",
        effective_date_choice=choice.value if isinstance(choice, EffectiveDateChoice) else str(choice),
        resolved_effective_date=resolved,
        created_by_user_id=actor_user_id,
    )
    db.add(period)
    # Mirror onto case current rate for legacy readers
    case.client_monthly_rate_inr = new_rate_inr
    db.flush()
    return period


# ---------------------------------------------------------------------------
# Add-on valuation
# ---------------------------------------------------------------------------


def add_on_client_amount(case: Case, session: TherapySession) -> tuple[float | None, str | None]:
    """Value add-on from configured additional-session rate; never from duration."""
    kind = effective_add_on_kind(session)
    if kind is None:
        return None, None
    # Configured additional rate: per-session client rate (PER_SESSION) or explicit package additional.
    if case.billing_type == BillingType.PER_SESSION:
        rate = float(case.client_rate_per_session_inr or 0)
    else:
        # Package/monthly add-on beyond entitlement uses client_rate_per_session if set
        rate = float(case.client_rate_per_session_inr or 0)
    if rate <= 0:
        return None, BillingCalcExceptionCode.MISSING_ADD_ON_RATE.value
    return round(rate, 2), None


# ---------------------------------------------------------------------------
# Orchestration used by ensure_period_charges
# ---------------------------------------------------------------------------


def build_step6_monthly_periods(
    db: Session,
    case: Case,
    *,
    billing_month: str,
) -> tuple[list[EffectiveRatePeriod], set[date], list[dict]]:
    month_start, month_end = _month_bounds(billing_month)
    periods, ex = client_rate_periods_for_month(
        db, case, month_start=month_start, month_end=month_end
    )
    # Primary therapist for leave: active assignment overlapping month
    therapist_id = None
    wins, _ = assignment_windows_for_month(
        db, case_id=case.id, month_start=month_start, month_end=month_end
    )
    if wins and wins[0].meta.get("therapist_user_id"):
        therapist_id = int(wins[0].meta["therapist_user_id"])
    leave_dates, leave_ex = deductible_leave_dates_for_month(
        db,
        case=case,
        therapist_user_id=therapist_id,
        month_start=month_start,
        month_end=month_end,
    )
    ex.extend(leave_ex)
    return periods, leave_dates, ex


def persist_calc_exceptions(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    exceptions: list[dict],
) -> None:
    for e in exceptions:
        code = e.get("code") or "UNKNOWN"
        msg = (e.get("message") or code)[:512]
        existing = db.scalars(
            select(BillingCalcException).where(
                BillingCalcException.case_id == case_id,
                BillingCalcException.ledger_month == billing_month,
                BillingCalcException.code == code,
                BillingCalcException.resolved.is_(False),
            )
        ).first()
        if existing:
            existing.message = msg
            continue
        db.add(
            BillingCalcException(
                case_id=case_id,
                ledger_month=billing_month,
                code=code,
                message=msg,
                session_id=e.get("session_id"),
            )
        )
    db.flush()
