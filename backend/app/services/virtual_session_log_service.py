"""Virtual session log rows for absence, leave, and pending approvals."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.daily_log import LogApprovalStatus
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.user import User


def _dispute_status(db: Session, session_id: int) -> str:
    disputed = db.scalars(
        select(SupportTicket).where(
            SupportTicket.disputed_session_id == session_id,
            SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
        )
    ).first()
    return "DISPUTED" if disputed else "NONE"


def serialize_virtual_log(
    db: Session,
    session: TherapySession,
    case: Case,
    *,
    include_clinical: bool = True,
    approval_status: LogApprovalStatus = LogApprovalStatus.APPROVED,
    attendance_status: str | None = None,
    status_label: str | None = None,
    absence_reason: str | None = None,
) -> dict:
    if attendance_status is None:
        attendance_status = "THERAPIST_LEAVE"
        absence_req = None
        if session.status == SessionStatus.CLIENT_ABSENT:
            absence_req = db.scalars(
                select(SessionAbsenceRequest).where(
                    SessionAbsenceRequest.session_id == session.id,
                    SessionAbsenceRequest.status == SessionAbsenceStatus.APPROVED,
                )
            ).first()
            if absence_req and absence_req.absence_type == SessionAbsenceType.CLIENT_ABSENT:
                attendance_status = "CLIENT_LEAVE"
            else:
                attendance_status = "CLIENT_ABSENT"

    if status_label is None:
        pending = approval_status == LogApprovalStatus.PENDING
        if attendance_status == "THERAPIST_LEAVE":
            status_label = "Therapist Leave (pending approval)" if pending else "Therapist Leave"
        elif attendance_status == "CLIENT_LEAVE":
            status_label = "Client Leave (pending approval)" if pending else "Client Leave"
        elif attendance_status == "CLIENT_ABSENT":
            status_label = "Child Absent (pending approval)" if pending else "Child Absent"
        else:
            status_label = attendance_status

    sub_dt = datetime.combine(session.scheduled_date, datetime.min.time(), tzinfo=timezone.utc)
    res = {
        "id": -session.id,
        "session_id": session.id,
        "case_id": session.case_id,
        "case_code": case.case_code if case else None,
        "child_name": case.child.full_name if (case and case.child) else None,
        "scheduled_date": session.scheduled_date,
        "actual_start_at": session.actual_start_at,
        "actual_end_at": session.actual_end_at,
        "edited_start_at": getattr(session, "edited_start_at", None),
        "edited_end_at": getattr(session, "edited_end_at", None),
        "actual_times_edited": bool(getattr(session, "actual_times_edited", False)),
        "actual_times_edit_reason": getattr(session, "actual_times_edit_reason", None),
        "duplicate_day_session": bool(getattr(session, "is_additional_visit", False)),
        "status_label": status_label,
        "attendance_status": attendance_status,
        "submitted_at": sub_dt,
        "approval_status": approval_status,
        "late_addition": False,
        "can_edit": False,
        "can_resubmit": False,
        "absence_reason": absence_reason,
        "dispute_status": _dispute_status(db, session.id),
    }
    if include_clinical:
        res.update(
            {
                "session_notes": None,
                "activities_done": None,
                "observations": None,
                "parent_notes": None,
            }
        )
    return res


def _leave_case_ids(leave: TherapistLeave) -> list[int]:
    if leave.case_ids:
        return [int(x) for x in leave.case_ids]
    if leave.case_id:
        return [int(leave.case_id)]
    return []


def collect_virtual_logs(
    db: Session,
    *,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
    month: str | None = None,
    product_module: str | None = None,
    approval_status_filter: LogApprovalStatus | None = None,
    late_addition: bool | None = None,
    include_clinical: bool = True,
    case_scope_ids: set[int] | None = None,
) -> list[dict]:
    """Build virtual log dicts for approved and pending absence/leave rows."""
    if late_addition is True:
        return []

    virtual_logs: list[dict] = []
    seen_session_ids: set[int] = set()

    def _month_ok(scheduled_date) -> bool:
        if not month:
            return True
        return scheduled_date.strftime("%b %Y") == month

    def _append(session: TherapySession, **kwargs) -> None:
        if session.id in seen_session_ids:
            return
        case = session.case or db.get(Case, session.case_id)
        if not case:
            return
        if case_scope_ids is not None and session.case_id not in case_scope_ids:
            return
        if case_id and session.case_id != case_id:
            return
        if therapist_user_id and session.therapist_user_id != therapist_user_id:
            return
        if product_module and (case.product_module or "").strip().lower() != product_module.strip().lower():
            return
        if not _month_ok(session.scheduled_date):
            return
        approval = kwargs.pop("approval_status", LogApprovalStatus.APPROVED)
        if approval_status_filter is not None and approval != approval_status_filter:
            return
        seen_session_ids.add(session.id)
        virtual_logs.append(serialize_virtual_log(db, session, case, include_clinical=include_clinical, approval_status=approval, **kwargs))

    approved_stmt = select(TherapySession).where(
        TherapySession.status.in_([SessionStatus.CLIENT_ABSENT, SessionStatus.THERAPIST_LEAVE])
    )
    if therapist_user_id:
        approved_stmt = approved_stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if case_id:
        approved_stmt = approved_stmt.where(TherapySession.case_id == case_id)
    if product_module:
        approved_stmt = approved_stmt.join(Case, TherapySession.case_id == Case.id).where(
            Case.product_module == product_module
        )
    for session in db.scalars(approved_stmt).all():
        _append(session)

    pending_absence_stmt = (
        select(SessionAbsenceRequest)
        .join(TherapySession, SessionAbsenceRequest.session_id == TherapySession.id)
        .where(SessionAbsenceRequest.status == SessionAbsenceStatus.PENDING_APPROVAL)
    )
    if therapist_user_id:
        pending_absence_stmt = pending_absence_stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if case_id:
        pending_absence_stmt = pending_absence_stmt.where(TherapySession.case_id == case_id)
    if product_module:
        pending_absence_stmt = pending_absence_stmt.join(Case, TherapySession.case_id == Case.id).where(
            Case.product_module == product_module
        )
    for row in db.scalars(pending_absence_stmt).all():
        session = row.session or db.get(TherapySession, row.session_id)
        if not session:
            continue
        if row.absence_type == SessionAbsenceType.CLIENT_ABSENT:
            _append(
                session,
                approval_status=LogApprovalStatus.PENDING,
                attendance_status="CLIENT_ABSENT",
                absence_reason=row.reason or row.notes,
            )
        else:
            _append(
                session,
                approval_status=LogApprovalStatus.PENDING,
                attendance_status="THERAPIST_LEAVE",
                absence_reason=row.reason or row.notes,
            )

    leave_stmt = select(TherapistLeave).where(TherapistLeave.status == LeaveStatus.PENDING)
    if therapist_user_id:
        leave_stmt = leave_stmt.where(TherapistLeave.therapist_user_id == therapist_user_id)
    for leave in db.scalars(leave_stmt).all():
        case_ids = _leave_case_ids(leave)
        if case_id and case_id not in case_ids:
            continue
        if not case_ids:
            continue
        session_stmt = select(TherapySession).where(
            TherapySession.therapist_user_id == leave.therapist_user_id,
            TherapySession.case_id.in_(case_ids),
            TherapySession.scheduled_date >= leave.start_date,
            TherapySession.scheduled_date <= leave.end_date,
            TherapySession.status.in_([SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS]),
        )
        if case_id:
            session_stmt = session_stmt.where(TherapySession.case_id == case_id)
        if product_module:
            session_stmt = session_stmt.join(Case, TherapySession.case_id == Case.id).where(
                Case.product_module == product_module
            )
        for session in db.scalars(session_stmt).all():
            _append(
                session,
                approval_status=LogApprovalStatus.PENDING,
                attendance_status="THERAPIST_LEAVE",
                absence_reason=leave.reason,
            )

    return virtual_logs
