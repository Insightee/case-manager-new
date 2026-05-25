from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import get_allowed_case_product_modules, user_has_feature
from app.core.permissions import user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.case_status_request import CaseStatusRequest, CaseStatusRequestStatus
from app.models.client_billing import ClientInvoice, ClientPayment, ClientPaymentStatus
from app.models.clinical import ObservationChecklist, ObservationChecklistStatus
from app.models.iep_plan import IepPlan, IepPlanStatus
from app.models.invoice import Invoice, InvoiceStatus
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


WIDGET_ITEM_LIMIT = 8

_HOME_OPERATIONAL_ROLES = frozenset({"SUPER_ADMIN", "ADMIN", "CASE_MANAGER", "SUPERVISOR"})


def user_may_see_reschedules_widget(user: User) -> bool:
    """Scheduling queue — not for HR/FINANCE-only home roles."""
    role_names = set(user.role_names or [])
    if not role_names.intersection(_HOME_OPERATIONAL_ROLES):
        return False
    if not user_has_feature(user, "cases"):
        return False
    return (
        user_has_permission(user, "case.read.team")
        or user_has_permission(user, "case.read.all")
        or user_has_permission(user, "slot.book_any")
    )


def widget_section_logs(db: Session, user: User, *, limit: int = WIDGET_ITEM_LIMIT) -> dict | None:
    if not user_has_permission(user, "daily_log.review") or not user_has_feature(user, "session_logs"):
        return None
    log_stmt = (
        select(DailyLog, Case, Child)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .join(Case, TherapySession.case_id == Case.id)
        .join(Child, Case.child_id == Child.id)
        .where(DailyLog.approval_status == LogApprovalStatus.PENDING)
        .order_by(DailyLog.created_at.desc())
        .limit(limit)
    )
    log_stmt = apply_case_scope(log_stmt, user)
    log_rows = db.execute(log_stmt).all()
    count_stmt = (
        select(func.count())
        .select_from(DailyLog)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .join(Case, TherapySession.case_id == Case.id)
        .where(DailyLog.approval_status == LogApprovalStatus.PENDING)
    )
    count_stmt = apply_case_scope(count_stmt, user)
    return {
        "count": int(db.scalar(count_stmt) or 0),
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


def widget_section_reports(db: Session, user: User, *, limit: int = WIDGET_ITEM_LIMIT) -> dict | None:
    if not user_has_permission(user, "monthly_report.approve") or not user_has_feature(user, "reports"):
        return None
    items, queue_meta = list_queue_admin(db, user, page=1, page_size=limit, report_type=None)
    return {
        "count": int(queue_meta.get("total") or len(items)),
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


def widget_section_tickets(db: Session, user: User, *, limit: int = WIDGET_ITEM_LIMIT) -> dict | None:
    if not user_has_permission(user, "ticket.manage") or not user_has_feature(user, "tickets"):
        return None
    ticket_stmt = (
        select(SupportTicket, Case, Child)
        .outerjoin(Case, SupportTicket.case_id == Case.id)
        .outerjoin(Child, Case.child_id == Child.id)
        .where(SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]))
        .order_by(SupportTicket.updated_at.desc())
        .limit(limit)
    )
    ticket_stmt = apply_case_scope(ticket_stmt, user)
    ticket_rows = db.execute(ticket_stmt).all()
    count_stmt = (
        select(func.count())
        .select_from(SupportTicket)
        .outerjoin(Case, SupportTicket.case_id == Case.id)
        .where(SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]))
    )
    count_stmt = apply_case_scope(count_stmt, user)
    return {
        "count": int(db.scalar(count_stmt) or 0),
        "items": [
            _row(
                case.case_code if case else None,
                child.full_name if child else None,
                case.id if case else None,
                id=t.id,
                subject=t.subject,
                status=t.status.value if hasattr(t.status, "value") else t.status,
                href="/admin/support?tab=tickets",
            )
            for t, case, child in ticket_rows
        ],
    }


def widget_section_billing(db: Session, user: User, *, limit: int = WIDGET_ITEM_LIMIT) -> dict | None:
    if not user_has_permission(user, "invoice.approve"):
        return None
    if not (user_has_feature(user, "invoices") or user_has_feature(user, "dashboard")):
        return None
    allowed = get_allowed_case_product_modules(user)
    scoped_therapist_ids = None
    if allowed is not None:
        if not allowed:
            scoped_therapist_ids = []
        else:
            scoped_therapist_ids = list(
                db.scalars(
                    select(CaseAssignment.therapist_user_id)
                    .join(Case, CaseAssignment.case_id == Case.id)
                    .where(
                        CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                        Case.product_module.in_(allowed),
                    )
                    .distinct()
                ).all()
            )
    invoice_base = select(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW)
    count_stmt = select(func.count()).select_from(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW)
    if scoped_therapist_ids is not None:
        if not scoped_therapist_ids:
            invoice_base = invoice_base.where(Invoice.id == -1)
            count_stmt = count_stmt.where(Invoice.id == -1)
        else:
            invoice_base = invoice_base.where(Invoice.therapist_user_id.in_(scoped_therapist_ids))
            count_stmt = count_stmt.where(Invoice.therapist_user_id.in_(scoped_therapist_ids))
    rows = list(db.scalars(invoice_base.order_by(Invoice.updated_at.desc()).limit(limit)).all())
    return {
        "count": int(db.scalar(count_stmt) or 0),
        "items": [
            {
                "id": inv.id,
                "label": f"Therapist #{inv.therapist_user_id} · {inv.month}",
                "case_id": None,
                "case_code": None,
                "child_name": None,
                "month": inv.month,
                "amount_inr": float(inv.amount_inr),
                "status": inv.status.value if hasattr(inv.status, "value") else inv.status,
                "href": "/admin/invoices",
            }
            for inv in rows
        ],
    }


def _count_scoped(db: Session, user: User, stmt) -> int:
    return int(db.scalar(apply_case_scope(stmt, user)) or 0)


def build_ops_counts(db: Session, user: User) -> dict:
    """Role-gated operational counts for dashboard KPIs."""
    counts: dict = {}
    today = date.today()

    if user_has_permission(user, "monthly_report.approve"):
        obs_chk_stmt = (
            select(func.count())
            .select_from(ObservationChecklist)
            .join(Case, ObservationChecklist.case_id == Case.id)
            .where(ObservationChecklist.status == ObservationChecklistStatus.SUBMITTED.value)
        )
        counts["observation_checklists_pending"] = _count_scoped(db, user, obs_chk_stmt)

        overdue_stmt = (
            select(func.count())
            .select_from(ObservationChecklist)
            .join(Case, ObservationChecklist.case_id == Case.id)
            .where(
                ObservationChecklist.due_at < today,
                ObservationChecklist.status.in_(
                    [ObservationChecklistStatus.DRAFT.value, ObservationChecklistStatus.REJECTED.value]
                ),
            )
        )
        counts["observation_checklists_overdue"] = _count_scoped(db, user, overdue_stmt)

        if user_has_feature(user, "reports"):
            obs_rep_stmt = (
                select(func.count())
                .select_from(ObservationReport)
                .join(Case, ObservationReport.case_id == Case.id)
                .where(ObservationReport.status == ReportStatus.UNDER_REVIEW)
            )
            counts["observation_reports_in_review"] = _count_scoped(db, user, obs_rep_stmt)

    if user_has_permission(user, "case.update"):
        sr_stmt = (
            select(func.count())
            .select_from(CaseStatusRequest)
            .join(Case, CaseStatusRequest.case_id == Case.id)
            .where(CaseStatusRequest.status == CaseStatusRequestStatus.PENDING)
        )
        counts["status_requests_pending"] = _count_scoped(db, user, sr_stmt)

    if user_has_permission(user, "invoice.approve") and (
        user_has_feature(user, "invoices") or user_has_feature(user, "dashboard")
    ):
        pay_stmt = (
            select(func.count())
            .select_from(ClientPayment)
            .join(ClientInvoice, ClientPayment.client_invoice_id == ClientInvoice.id)
            .join(Case, ClientInvoice.case_id == Case.id)
            .where(ClientPayment.payment_status == ClientPaymentStatus.PENDING_REVIEW)
        )
        counts["client_payments_pending_review"] = _count_scoped(db, user, pay_stmt)

    if user_has_permission(user, "iep.read") and user_has_feature(user, "iep"):
        iep_data = iep_svc.build_iep_dashboard(db, user, include_closed=False)
        summary = iep_data.get("summary", {})
        counts["iep_attention"] = int(summary.get("missing", 0)) + int(summary.get("internal_only", 0))
        draft_stmt = (
            select(func.count())
            .select_from(IepPlan)
            .join(Case, IepPlan.case_id == Case.id)
            .where(IepPlan.status == IepPlanStatus.DRAFT.value)
        )
        counts["iep_plans_draft"] = _count_scoped(db, user, draft_stmt)

    return counts


def widget_section_observations(db: Session, user: User, *, limit: int = WIDGET_ITEM_LIMIT) -> dict | None:
    if not user_has_permission(user, "monthly_report.approve"):
        return None
    stmt = (
        select(ObservationChecklist, Case, Child, User)
        .join(Case, ObservationChecklist.case_id == Case.id)
        .outerjoin(Child, Case.child_id == Child.id)
        .outerjoin(User, ObservationChecklist.therapist_user_id == User.id)
        .where(ObservationChecklist.status == ObservationChecklistStatus.SUBMITTED.value)
        .order_by(ObservationChecklist.submitted_at.asc())
        .limit(limit)
    )
    stmt = apply_case_scope(stmt, user)
    rows = db.execute(stmt).all()
    count_stmt = (
        select(func.count())
        .select_from(ObservationChecklist)
        .join(Case, ObservationChecklist.case_id == Case.id)
        .where(ObservationChecklist.status == ObservationChecklistStatus.SUBMITTED.value)
    )
    count_stmt = apply_case_scope(count_stmt, user)
    today = date.today()
    return {
        "count": int(db.scalar(count_stmt) or 0),
        "items": [
            _row(
                case.case_code,
                " ".join(p for p in (child.first_name, child.last_name) if p).strip() if child else None,
                case.id,
                id=chk.id,
                label=f"Observation checklist · {therapist.full_name if therapist else 'Therapist'}",
                submitted_at=chk.submitted_at.isoformat() if chk.submitted_at else None,
                is_overdue=bool(chk.due_at and chk.due_at < today),
                href=f"/admin/workbench?section=observations&checklistId={chk.id}",
            )
            for chk, case, child, therapist in rows
        ],
    }


def widget_section_status_requests(db: Session, user: User, *, limit: int = WIDGET_ITEM_LIMIT) -> dict | None:
    if not user_has_permission(user, "case.update"):
        return None
    stmt = (
        select(CaseStatusRequest, Case, Child, User)
        .join(Case, CaseStatusRequest.case_id == Case.id)
        .outerjoin(Child, Case.child_id == Child.id)
        .outerjoin(User, CaseStatusRequest.requested_by_user_id == User.id)
        .where(CaseStatusRequest.status == CaseStatusRequestStatus.PENDING)
        .order_by(CaseStatusRequest.created_at.asc())
        .limit(limit)
    )
    stmt = apply_case_scope(stmt, user)
    rows = db.execute(stmt).all()
    count_stmt = (
        select(func.count())
        .select_from(CaseStatusRequest)
        .join(Case, CaseStatusRequest.case_id == Case.id)
        .where(CaseStatusRequest.status == CaseStatusRequestStatus.PENDING)
    )
    count_stmt = apply_case_scope(count_stmt, user)
    return {
        "count": int(db.scalar(count_stmt) or 0),
        "items": [
            _row(
                case.case_code,
                child.full_name if child else None,
                case.id,
                id=req.id,
                label=f"{req.from_status} → {req.to_status}",
                requested_by=therapist.full_name if therapist else None,
                href=f"/admin/cases/{case.id}?tab=overview",
            )
            for req, case, child, therapist in rows
        ],
    }


def widget_section_client_claims(db: Session, user: User, *, limit: int = WIDGET_ITEM_LIMIT) -> dict | None:
    if not user_has_permission(user, "invoice.approve"):
        return None
    if not (user_has_feature(user, "invoices") or user_has_feature(user, "dashboard")):
        return None
    stmt = (
        select(ClientPayment, ClientInvoice, Case, Child)
        .join(ClientInvoice, ClientPayment.client_invoice_id == ClientInvoice.id)
        .join(Case, ClientInvoice.case_id == Case.id)
        .join(Child, Case.child_id == Child.id)
        .where(ClientPayment.payment_status == ClientPaymentStatus.PENDING_REVIEW)
        .order_by(ClientPayment.paid_at.desc())
        .limit(limit)
    )
    stmt = apply_case_scope(stmt, user)
    rows = db.execute(stmt).all()
    count_stmt = (
        select(func.count())
        .select_from(ClientPayment)
        .join(ClientInvoice, ClientPayment.client_invoice_id == ClientInvoice.id)
        .join(Case, ClientInvoice.case_id == Case.id)
        .where(ClientPayment.payment_status == ClientPaymentStatus.PENDING_REVIEW)
    )
    count_stmt = apply_case_scope(count_stmt, user)
    return {
        "count": int(db.scalar(count_stmt) or 0),
        "items": [
            {
                "id": pay.id,
                "case_id": case.id,
                "case_code": case.case_code,
                "child_name": child.full_name if child else None,
                "label": f"Payment claim · ₹{float(pay.amount_inr):,.0f}",
                "invoice_number": inv.invoice_number,
                "href": f"/admin/invoices?tab=client&claims=pending&invoiceId={inv.id}",
            }
            for pay, inv, case, child in rows
        ],
    }


def build_admin_alerts(db: Session, user: User) -> list[dict]:
    alerts: list[dict] = []
    counts = build_ops_counts(db, user)
    if counts.get("observation_checklists_overdue", 0) > 0:
        alerts.append(
            {
                "id": "observation_overdue",
                "severity": "warning",
                "title": "Overdue observation checklists",
                "message": f"{counts['observation_checklists_overdue']} observation checklist(s) overdue",
                "href": "/admin/workbench?section=observations",
            }
        )
    if counts.get("observation_checklists_pending", 0) > 0:
        alerts.append(
            {
                "id": "observation_pending",
                "severity": "info",
                "title": "Observation checklists pending",
                "message": f"{counts['observation_checklists_pending']} awaiting review",
                "href": "/admin/workbench?section=observations",
            }
        )
    if counts.get("status_requests_pending", 0) > 0:
        alerts.append(
            {
                "id": "status_requests",
                "severity": "info",
                "title": "Status change requests",
                "message": f"{counts['status_requests_pending']} pending approval",
                "href": "/admin/workbench?section=status_requests",
            }
        )
    if counts.get("client_payments_pending_review", 0) > 0:
        alerts.append(
            {
                "id": "client_claims",
                "severity": "warning",
                "title": "Client payment claims",
                "message": f"{counts['client_payments_pending_review']} awaiting finance review",
                "href": "/admin/invoices?tab=client&claims=pending",
            }
        )
    return alerts


def widget_section_reschedules(db: Session, user: User, *, limit: int = WIDGET_ITEM_LIMIT) -> dict | None:
    if not user_may_see_reschedules_widget(user):
        return None
    slot_stmt = (
        select(TherapistSlot, Case, Child)
        .join(Case, TherapistSlot.case_id == Case.id)
        .join(Child, Case.child_id == Child.id)
        .where(
            TherapistSlot.approval_status == "PENDING_THERAPIST",
            TherapistSlot.status == SlotStatus.BOOKED,
        )
        .order_by(TherapistSlot.slot_date.asc(), TherapistSlot.start_time.asc())
        .limit(limit)
    )
    slot_stmt = apply_case_scope(slot_stmt, user)
    slot_rows = db.execute(slot_stmt).all()
    count_stmt = (
        select(func.count())
        .select_from(TherapistSlot)
        .join(Case, TherapistSlot.case_id == Case.id)
        .where(
            TherapistSlot.approval_status == "PENDING_THERAPIST",
            TherapistSlot.status == SlotStatus.BOOKED,
        )
    )
    count_stmt = apply_case_scope(count_stmt, user)
    return {
        "count": int(db.scalar(count_stmt) or 0),
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


def build_workbench_summary(db: Session, user: User) -> dict:
    sections: dict = {}

    observations = widget_section_observations(db, user)
    if observations:
        sections["observations"] = observations

    status_requests = widget_section_status_requests(db, user)
    if status_requests:
        sections["status_requests"] = status_requests

    client_claims = widget_section_client_claims(db, user)
    if client_claims:
        sections["client_claims"] = client_claims

    reports = widget_section_reports(db, user)
    if reports:
        sections["reports"] = reports

    logs = widget_section_logs(db, user)
    if logs:
        sections["logs"] = logs

    tickets = widget_section_tickets(db, user)
    if tickets:
        sections["tickets"] = tickets

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

    reschedules = widget_section_reschedules(db, user)
    if reschedules:
        sections["reschedules"] = reschedules

    return {"sections": sections}
