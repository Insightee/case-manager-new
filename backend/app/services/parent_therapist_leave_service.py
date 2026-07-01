from __future__ import annotations

from calendar import monthrange
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.services import leave_notification_service as leave_notify
from app.services import parent_service

_IMPACT_SESSION_STATUSES = (
    SessionStatus.THERAPIST_LEAVE,
    SessionStatus.CANCELLED,
    SessionStatus.SCHEDULED,
    SessionStatus.IN_PROGRESS,
)


def _parent_cases(db: Session, user_id: int, case_id: int | None) -> dict[int, Case]:
    child_ids = parent_service.child_ids_for_parent(db, user_id)
    if not child_ids:
        return {}
    stmt = select(Case).where(Case.child_id.in_(child_ids)).options(selectinload(Case.child))
    if case_id is not None:
        stmt = stmt.where(Case.id == case_id)
    return {c.id: c for c in db.scalars(stmt).all()}


def _leave_affects_case(leave: TherapistLeave, case_id: int, db: Session) -> bool:
    scoped = leave_notify._cases_for_leave_scope(db, leave)
    scoped_ids = {c.id for c in scoped}
    return case_id in scoped_ids


def _affected_dates(db: Session, leave: TherapistLeave, case_id: int) -> list[date]:
    session_dates = db.scalars(
        select(TherapySession.scheduled_date)
        .where(
            TherapySession.therapist_user_id == leave.therapist_user_id,
            TherapySession.case_id == case_id,
            TherapySession.scheduled_date >= leave.start_date,
            TherapySession.scheduled_date <= leave.end_date,
            TherapySession.status.in_(_IMPACT_SESSION_STATUSES),
        )
        .distinct()
    ).all()

    slot_dates = db.scalars(
        select(TherapistSlot.slot_date)
        .where(
            TherapistSlot.therapist_user_id == leave.therapist_user_id,
            TherapistSlot.case_id == case_id,
            TherapistSlot.slot_date >= leave.start_date,
            TherapistSlot.slot_date <= leave.end_date,
            or_(
                TherapistSlot.leave_block_leave_id == leave.id,
                TherapistSlot.status.in_((SlotStatus.BOOKED, SlotStatus.CANCELLED)),
            ),
        )
        .distinct()
    ).all()

    combined = {d for d in session_dates if d} | {d for d in slot_dates if d}
    return sorted(combined, reverse=True)


def _status_label(status: LeaveStatus) -> str:
    if status == LeaveStatus.APPROVED:
        return "Leave confirmed"
    if status == LeaveStatus.PENDING:
        return "Leave pending approval"
    return status.value.title()


def _overlaps_period(start: date, end: date, year: int | None, month: int | None) -> bool:
    if year is not None and (end.year < year or start.year > year):
        return False
    if month is None:
        return True
    y = year if year is not None else start.year
    period_start = date(y, month, 1)
    period_end = date(y, month, monthrange(y, month)[1])
    return start <= period_end and end >= period_start


def list_parent_therapist_leave_days(
    db: Session,
    user: User,
    *,
    case_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
) -> list[dict]:
    """Leave impact rows scoped to a parent's cases (one row per affected date)."""
    cases = _parent_cases(db, user.id, case_id)
    if not cases:
        return []

    leaves = db.scalars(
        select(TherapistLeave)
        .where(TherapistLeave.status.in_((LeaveStatus.APPROVED, LeaveStatus.PENDING)))
        .order_by(TherapistLeave.start_date.desc())
    ).all()

    therapist_names: dict[int, str | None] = {}
    out: list[dict] = []
    seen: set[tuple[int, int, date]] = set()

    for leave in leaves:
        therapist = db.get(User, leave.therapist_user_id)
        therapist_names[leave.therapist_user_id] = therapist.full_name if therapist else None

        for cid, case in cases.items():
            if not _leave_affects_case(leave, cid, db):
                continue

            dates = _affected_dates(db, leave, cid)
            child_name = case.child.full_name if case.child else None
            status_value = leave.status.value if hasattr(leave.status, "value") else str(leave.status)
            label = _status_label(leave.status)

            if dates:
                for day in dates:
                    if year is not None and day.year != year:
                        continue
                    if month is not None and day.month != month:
                        continue
                    key = (leave.id, cid, day)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(
                        {
                            "id": f"leave-{leave.id}-{cid}-{day.isoformat()}",
                            "leave_id": leave.id,
                            "case_id": cid,
                            "case_code": case.case_code,
                            "child_name": child_name,
                            "therapist_name": therapist_names.get(leave.therapist_user_id),
                            "scheduled_date": day,
                            "leave_end_date": None,
                            "reason": (leave.reason or "").strip() or None,
                            "status": status_value,
                            "status_label": label,
                        }
                    )
                continue

            start = leave.start_date
            end = leave.end_date
            if not _overlaps_period(start, end, year, month):
                continue

            key = (leave.id, cid, start)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "id": f"leave-{leave.id}-{cid}-{start.isoformat()}",
                    "leave_id": leave.id,
                    "case_id": cid,
                    "case_code": case.case_code,
                    "child_name": child_name,
                    "therapist_name": therapist_names.get(leave.therapist_user_id),
                    "scheduled_date": start,
                    "leave_end_date": end if end != start else None,
                    "reason": (leave.reason or "").strip() or None,
                    "status": status_value,
                    "status_label": label,
                }
            )

    out.sort(key=lambda row: (row["scheduled_date"], row["leave_id"], row["case_id"]), reverse=True)
    return out
