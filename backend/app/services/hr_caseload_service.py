"""HR caseload / reassignment lens aggregates."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.case_therapist_transition import (
    CaseTherapistTransition,
    CaseTherapistTransitionStatus,
)
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.services import case_service


def _pay_label(case: Case) -> str | None:
    mode = (case.compensation_mode or "").upper() if case.compensation_mode else ""
    fixed = case.therapist_fixed_pay_inr
    share = case.pay_share_amount_inr
    amount = fixed if fixed is not None else share
    if amount is None:
        return None
    if mode == "FIXED_LUMP" or fixed is not None:
        return f"₹{int(amount):,} lumpsum"
    return f"₹{int(amount):,}"


def build_hr_caseload(db: Session, *, include_pay: bool = True) -> dict[str, Any]:
    """Therapist-centric caseload with pending-reassignment signals."""
    cases = list(
        db.scalars(
            select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
        ).all()
    )
    case_ids = [c.id for c in cases]
    assignments = []
    if case_ids:
        assignments = list(
            db.scalars(
                select(CaseAssignment)
                .where(
                    CaseAssignment.case_id.in_(case_ids),
                    CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                )
                .order_by(CaseAssignment.id.desc())
            ).all()
        )
    assign_by_case: dict[int, CaseAssignment] = {}
    for a in assignments:
        if a.case_id not in assign_by_case:
            assign_by_case[a.case_id] = a

    open_transitions: set[int] = set()
    if case_ids:
        open_transitions = set(
            db.scalars(
                select(CaseTherapistTransition.case_id).where(
                    CaseTherapistTransition.case_id.in_(case_ids),
                    CaseTherapistTransition.status.in_(
                        (
                            CaseTherapistTransitionStatus.SCHEDULED,
                            CaseTherapistTransitionStatus.ACTIVE,
                        )
                    ),
                )
            ).all()
        )

    therapist_ids = {a.therapist_user_id for a in assign_by_case.values()}
    therapists = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(therapist_ids or {-1}))).all()
    }

    today = date.today()
    end = today + timedelta(days=14)
    slot_rows = []
    if therapist_ids:
        slot_rows = db.execute(
            select(
                TherapistSlot.therapist_user_id,
                TherapistSlot.status,
                func.count(),
            )
            .where(
                TherapistSlot.therapist_user_id.in_(therapist_ids),
                TherapistSlot.slot_date >= today,
                TherapistSlot.slot_date <= end,
            )
            .group_by(TherapistSlot.therapist_user_id, TherapistSlot.status)
        ).all()
    slot_stats: dict[int, dict[str, int]] = defaultdict(
        lambda: {"available": 0, "booked": 0, "total": 0}
    )
    for tid, st, cnt in slot_rows:
        key = st.value if hasattr(st, "value") else str(st)
        slot_stats[tid]["total"] += int(cnt)
        if key == SlotStatus.AVAILABLE.value:
            slot_stats[tid]["available"] += int(cnt)
        elif key == SlotStatus.BOOKED.value:
            slot_stats[tid]["booked"] += int(cnt)

    case_items: list[dict[str, Any]] = []
    by_therapist: dict[int, list[int]] = defaultdict(list)
    pending_reassignment = 0

    for case in cases:
        assign = assign_by_case.get(case.id)
        therapist = therapists.get(assign.therapist_user_id) if assign else None
        status_val = case.status.value if hasattr(case.status, "value") else str(case.status)
        assignment_ending = bool(assign and assign.end_date is not None)
        needs_therapist = status_val == CaseStatus.ACTIVE.value and assign is None
        pending_status = status_val in (
            CaseStatus.PENDING_REPLACEMENT.value,
            CaseStatus.PENDING_ALLOTMENT.value,
        )
        in_transition = case.id in open_transitions
        is_pending = assignment_ending or needs_therapist or pending_status or in_transition
        if is_pending:
            pending_reassignment += 1

        if therapist:
            by_therapist[therapist.id].append(case.id)

        item: dict[str, Any] = {
            "id": case.id,
            "case_code": case.case_code,
            "child_name": case_service.case_child_display_name(case),
            "therapist_user_id": therapist.id if therapist else None,
            "therapist_name": therapist.full_name if therapist else None,
            "status": status_val,
            "product_module": case.product_module,
            "region": case.region,
            "pending_reassignment": is_pending,
            "assignment_end_date": assign.end_date.isoformat()
            if assign and assign.end_date
            else None,
        }
        if include_pay:
            item["compensation_mode"] = case.compensation_mode
            item["therapist_fixed_pay_inr"] = case.therapist_fixed_pay_inr
            item["pay_share_amount_inr"] = case.pay_share_amount_inr
            item["pay_label"] = _pay_label(case)
        case_items.append(item)

    therapist_rows: list[dict[str, Any]] = []
    for tid, _cids in by_therapist.items():
        t = therapists.get(tid)
        if not t:
            continue
        stats = slot_stats.get(tid, {"available": 0, "booked": 0, "total": 0})
        fill_pct = None
        if stats["total"]:
            fill_pct = round(100.0 * stats["booked"] / stats["total"], 1)
        pending_count = sum(
            1 for c in case_items if c["therapist_user_id"] == tid and c["pending_reassignment"]
        )
        therapist_rows.append(
            {
                "therapist_user_id": tid,
                "therapist_name": t.full_name,
                "is_active": t.is_active,
                "employment_status": t.employment_status.value if t.employment_status else None,
                "case_count": len(by_therapist[tid]),
                "pending_reassignment_count": pending_count,
                "slots_available_14d": stats["available"],
                "slots_booked_14d": stats["booked"],
                "slots_total_14d": stats["total"],
                "slot_fill_pct_14d": fill_pct,
                "slots_full": stats["total"] > 0 and stats["available"] == 0,
            }
        )
    therapist_rows.sort(
        key=lambda r: (-r["pending_reassignment_count"], -r["case_count"], r["therapist_name"] or "")
    )

    return {
        "cases": case_items,
        "therapists": therapist_rows,
        "summary": {
            "case_count": len(case_items),
            "therapist_count": len(therapist_rows),
            "pending_reassignment": pending_reassignment,
        },
        "include_pay": include_pay,
    }
