from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import user_has_feature
from app.core.permissions import user_has_permission
from app.models.case import Case
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.models.child import Child
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.incident import Incident, OPEN_INCIDENT_STATUSES
from app.models.report import MonthlyReport, ObservationReport, ParentReviewStatus, ReportStatus
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.services import admin_iep_service as iep_svc
from app.services.admin_report_service import list_queue_admin
from app.services.admin_scope_service import apply_case_scope


def _row(case_code: str | None, child_name: str | None, case_id: int | None, **extra) -> dict:
    return {"case_code": case_code, "child_name": child_name, "case_id": case_id, **extra}


def build_workbench_summary(db: Session, user: User) -> dict:
    sections: dict = {}

    if user_has_permission(user, "monthly_report.approve") and user_has_feature(user, "reports"):
        items, _ = list_queue_admin(db, user, page=1, page_size=8, report_type=None)
        sections["reports"] = {
            "count": len(items),
            "items": [
                {
                    "id": i.id,
                    "report_type": i.report_type,
                    "label": i.label,
                    "case_id": i.case_id,
                    "case_code": i.case_code,
                    "child_name": i.child_name,
                    "status": i.status,
                    "href": f"/admin/reports?reportId={i.id}&type={i.report_type}&case_id={i.case_id}",
                }
                for i in items
            ],
        }

    if user_has_permission(user, "daily_log.review") and user_has_feature(user, "session_logs"):
        log_stmt = (
            select(DailyLog, Case, Child)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .join(Case, TherapySession.case_id == Case.id)
            .join(Child, Case.child_id == Child.id)
            .where(DailyLog.approval_status == LogApprovalStatus.PENDING)
            .order_by(DailyLog.created_at.desc())
            .limit(8)
        )
        log_stmt = apply_case_scope(log_stmt, user)
        log_rows = db.execute(log_stmt).all()
        sections["logs"] = {
            "count": len(log_rows),
            "items": [
                _row(
                    case.case_code,
                    child.full_name if child else None,
                    case.id,
                    id=log.id,
                    href=f"/admin/cases/{case.id}?tab=logs",
                )
                for log, case, child in log_rows
            ],
        }

    if user_has_permission(user, "ticket.manage") and user_has_feature(user, "tickets"):
        ticket_stmt = (
            select(SupportTicket, Case, Child)
            .outerjoin(Case, SupportTicket.case_id == Case.id)
            .outerjoin(Child, Case.child_id == Child.id)
            .where(SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]))
            .order_by(SupportTicket.updated_at.desc())
            .limit(8)
        )
        ticket_stmt = apply_case_scope(ticket_stmt, user)
        ticket_rows = db.execute(ticket_stmt).all()
        sections["tickets"] = {
            "count": len(ticket_rows),
            "items": [
                _row(
                    case.case_code if case else None,
                    child.full_name if child else None,
                    case.id if case else None,
                    id=t.id,
                    subject=t.subject,
                    status=t.status.value if hasattr(t.status, "value") else t.status,
                    href=f"/admin/support?tab=tickets",
                )
                for t, case, child in ticket_rows
            ],
        }

    if user_has_permission(user, "incident.read_sensitive") and user_has_feature(user, "incidents"):
        inc_stmt = (
            select(Incident, Case, Child)
            .outerjoin(Case, Incident.case_id == Case.id)
            .outerjoin(Child, Case.child_id == Child.id)
            .where(Incident.status.in_(list(OPEN_INCIDENT_STATUSES)))
            .order_by(Incident.created_at.desc())
            .limit(8)
        )
        inc_stmt = apply_case_scope(inc_stmt, user)
        inc_rows = db.execute(inc_stmt).all()
        sections["incidents"] = {
            "count": len(inc_rows),
            "items": [
                _row(
                    case.case_code if case else None,
                    child.full_name if child else None,
                    case.id if case else None,
                    id=inc.id,
                    title=inc.title,
                    status=inc.status.value if hasattr(inc.status, "value") else inc.status,
                    href=f"/admin/support?tab=incidents",
                )
                for inc, case, child in inc_rows
            ],
        }

    if user_has_permission(user, "iep.read") and user_has_feature(user, "iep"):
        iep_data = iep_svc.build_iep_dashboard(db, user, include_closed=False)
        attention = [r for r in iep_data.get("rows", []) if r.get("iep_status") in ("MISSING", "INTERNAL_ONLY")][:8]
        sections["iep"] = {
            "count": iep_data.get("summary", {}).get("missing", 0)
            + iep_data.get("summary", {}).get("internal_only", 0),
            "items": [
                _row(
                    r.get("case_code"),
                    r.get("child_name"),
                    r.get("case_id"),
                    iep_status=r.get("iep_status"),
                    href=f"/admin/iep",
                )
                for r in attention
            ],
        }

    role_names = {r.name for r in (user.roles or [])}
    can_meetings = user_has_permission(user, "case.read.team") and role_names.intersection(
        {"CASE_MANAGER", "ADMIN", "SUPER_ADMIN", "SUPERVISOR"}
    )
    if can_meetings:
        meet_stmt = (
            select(CaseManagerMeeting, Case, Child)
            .outerjoin(Case, CaseManagerMeeting.case_id == Case.id)
            .outerjoin(Child, Case.child_id == Child.id)
            .where(
                CaseManagerMeeting.status == MeetingStatus.SCHEDULED,
                CaseManagerMeeting.scheduled_date >= date.today(),
            )
            .order_by(CaseManagerMeeting.scheduled_date.asc())
            .limit(8)
        )
        role = user.roles[0].name if user.roles else ""
        if role == "CASE_MANAGER" and not user_has_permission(user, "admin.override"):
            meet_stmt = meet_stmt.where(CaseManagerMeeting.case_manager_user_id == user.id)
        elif role == "SUPERVISOR" and not user_has_permission(user, "admin.override"):
            meet_stmt = apply_case_scope(meet_stmt, user)
        meet_rows = db.execute(meet_stmt).all()
        sections["meetings"] = {
            "count": len(meet_rows),
            "items": [
                _row(
                    case.case_code if case else None,
                    child.full_name if child else None,
                    case.id if case else None,
                    id=m.id,
                    title=m.title or m.meeting_type.value,
                    scheduled_date=m.scheduled_date.isoformat(),
                    meeting_type=m.meeting_type.value,
                    href=f"/admin/cm-meetings?case_id={case.id}" if case else "/admin/cm-meetings",
                )
                for m, case, child in meet_rows
            ],
        }

    can_reschedules = user_has_feature(user, "cases") and (
        user_has_permission(user, "case.read.team")
        or user_has_permission(user, "case.read.all")
        or user_has_permission(user, "slot.book_any")
    )
    if can_reschedules:
        slot_stmt = (
            select(TherapistSlot, Case, Child)
            .join(Case, TherapistSlot.case_id == Case.id)
            .join(Child, Case.child_id == Child.id)
            .where(
                TherapistSlot.approval_status == "PENDING_THERAPIST",
                TherapistSlot.status == SlotStatus.BOOKED,
            )
            .order_by(TherapistSlot.slot_date.asc(), TherapistSlot.start_time.asc())
            .limit(8)
        )
        slot_stmt = apply_case_scope(slot_stmt, user)
        slot_rows = db.execute(slot_stmt).all()
        sections["reschedules"] = {
            "count": len(slot_rows),
            "items": [
                _row(
                    case.case_code,
                    child.full_name if child else None,
                    case.id,
                    id=slot.id,
                    label=f"Reschedule pending · {slot.slot_date.isoformat()}",
                    scheduled_date=slot.slot_date.isoformat(),
                    status="PENDING_THERAPIST",
                    href=f"/admin/cases/{case.id}?tab=scheduling&slotId={slot.id}",
                )
                for slot, case, child in slot_rows
            ],
        }

    return {"sections": sections}
