from __future__ import annotations

from typing import Optional

import csv
import io
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.config import settings
from app.core.database import get_db
from app.core.pagination import paginate_query, paginated_response
from app.schemas.pagination import PaginatedList
from app.core.module_access import (
    get_allowed_case_product_modules,
    get_user_features,
    modules_for_api,
    user_has_feature,
    validate_module_assignments,
)
from app.core.modules import ROLE_DEFAULT_MODULES, module_catalog_for_api
from app.core.permissions import case_scope_check, require_permission, user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.daily_log import DailyLog
from app.models.invoice import Invoice, InvoiceStatus
from app.models.report import MonthlyReport, ReportStatus
from app.schemas.admin_reports import (
    AdminReportDetail,
    AdminReportListItem,
    AdminReportSummary,
    BulkReportAction,
    CmReviewAction,
    BulkReportResult,
)
from app.services import admin_report_service as admin_report_svc
from app.models.session import Session as TherapySession
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import InviteToken, User
from app.schemas.admin_case_pipeline import AdminCasePipelineBoard
from app.schemas.admin_iep import AdminIepDashboard
from app.schemas.clinical import ObservationChecklistReview
from app.schemas.iep_plan import IepPlanSave
from app.schemas.therapist_onboarding import (
    TherapistBulkOnboardRequest,
    TherapistOnboardCreate,
    TherapistOnboardResult,
)
from app.schemas.therapist_profile import (
    TherapistProfileAdminCreate,
    TherapistProfileRead,
    TherapistProfileReview,
    TherapistProfileUpdate,
)
from app.services import admin_case_pipeline_service as case_pipeline_svc
from app.services import admin_iep_service as admin_iep_svc
from app.services import therapist_onboarding_service as therapist_onboard_svc
from app.schemas.therapist_review import (
    TherapistReviewSummary,
    TherapistReviewsResponse,
    TherapistSessionReviewRead,
)
from app.schemas.allotment import CaseAllotRequest, ChildCreate, FamilyCreate
from app.schemas.user import InviteCreate, UserCreate, UserRead, UserUpdate
from app.services import auth_service, case_service, log_service, therapist_profile_service as profile_svc
from app.services.admin_scope_service import apply_case_scope
from app.services import therapist_review_service as review_svc
from app.core.permissions import RoleName

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_dashboard_user(user: User = Depends(get_current_user)) -> User:
    if not (
        user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "admin.override")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user


def _case_filter(allowed: set[str] | None):
    if allowed is None:
        return []
    if not allowed:
        return [Case.id == -1]
    return [Case.product_module.in_(allowed)]


@router.get("/modules")
def list_product_modules(user: User = Depends(require_permission("user.manage"))):
    return {
        "modules": module_catalog_for_api(),
        "role_defaults": ROLE_DEFAULT_MODULES,
    }


def _workbench_user(user: User = Depends(get_current_user)) -> User:
    if not (
        user_has_permission(user, "case.read.team")
        and (
            user_has_permission(user, "monthly_report.approve")
            or user_has_permission(user, "daily_log.review")
        )
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user


@router.get("/workbench/summary")
def workbench_summary(
    user: User = Depends(_workbench_user),
    db: Session = Depends(get_db),
):
    from app.services import admin_workbench_service as workbench_svc

    return workbench_svc.build_workbench_summary(db, user)


@router.get("/home")
def admin_home(
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    from app.services import admin_home_service

    return admin_home_service.build_admin_home(db, user)


@router.get("/audit")
def admin_audit_list(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    case_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[int] = None,
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    from app.services import audit_service

    try:
        return audit_service.list_audit_events(
            db,
            user,
            entity_type=entity_type,
            entity_id=entity_id,
            case_id=case_id,
            limit=limit,
            cursor=cursor,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.get("/cases/{case_id}/timeline")
def admin_case_timeline(
    case_id: int,
    limit: int = Query(40, ge=1, le=100),
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    from app.services import audit_service

    try:
        return {"items": audit_service.case_timeline(db, user, case_id, limit=limit)}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.get("/dashboard/summary")
def dashboard_summary(
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    allowed_cases = get_allowed_case_product_modules(user)

    def _count_case_status(status: CaseStatus) -> int:
        stmt = select(func.count()).select_from(Case).where(Case.status == status)
        stmt = apply_case_scope(stmt, user)
        return db.scalar(stmt) or 0

    pending_stmt = (
        select(Case.id, Case.case_code, Case.service_type, Case.status, Child.first_name, Child.last_name)
        .join(Child, Case.child_id == Child.id)
        .where(Case.status == CaseStatus.PENDING_ALLOTMENT)
    )
    pending_stmt = apply_case_scope(pending_stmt, user).order_by(Case.created_at.desc()).limit(6)
    pending_rows = db.execute(pending_stmt).all()

    report_stmt = (
        select(
            MonthlyReport.id,
            MonthlyReport.case_id,
            MonthlyReport.month,
            MonthlyReport.status,
            Case.case_code,
            Child.first_name,
            Child.last_name,
        )
        .join(Case, MonthlyReport.case_id == Case.id)
        .join(Child, Case.child_id == Child.id)
        .where(MonthlyReport.status == ReportStatus.UNDER_REVIEW)
    )
    report_stmt = apply_case_scope(report_stmt, user).order_by(MonthlyReport.updated_at.desc()).limit(6)
    report_rows = db.execute(report_stmt).all() if user_has_feature(user, "reports") else []

    invoice_rows = []
    invoices_pending = 0
    if user_has_feature(user, "invoices"):
        scoped_therapist_ids = None
        if allowed_cases is not None:
            if not allowed_cases:
                scoped_therapist_ids = []
            else:
                scoped_therapist_ids = list(
                    db.scalars(
                        select(CaseAssignment.therapist_user_id)
                        .join(Case, CaseAssignment.case_id == Case.id)
                        .where(
                            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                            Case.product_module.in_(allowed_cases),
                        )
                        .distinct()
                    ).all()
                )
        invoice_base = select(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW)
        if scoped_therapist_ids is not None:
            if not scoped_therapist_ids:
                invoice_base = invoice_base.where(Invoice.id == -1)
            else:
                invoice_base = invoice_base.where(Invoice.therapist_user_id.in_(scoped_therapist_ids))
        invoice_rows = list(
            db.scalars(invoice_base.order_by(Invoice.updated_at.desc()).limit(6)).all()
        )
        count_stmt = select(func.count()).select_from(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW)
        if scoped_therapist_ids is not None:
            if not scoped_therapist_ids:
                count_stmt = count_stmt.where(Invoice.id == -1)
            else:
                count_stmt = count_stmt.where(Invoice.therapist_user_id.in_(scoped_therapist_ids))
        invoices_pending = db.scalar(count_stmt) or 0

    ticket_filters = []
    if allowed_cases is not None:
        if allowed_cases:
            ticket_filters.append(
                or_(SupportTicket.product_module.in_(allowed_cases), SupportTicket.product_module.is_(None))
            )
        else:
            ticket_filters.append(SupportTicket.id == -1)

    ticket_rows = []
    open_tickets = 0
    if user_has_feature(user, "tickets"):
        ticket_rows = list(
            db.scalars(
                select(SupportTicket)
                .where(SupportTicket.status == TicketStatus.OPEN, *ticket_filters)
                .order_by(SupportTicket.updated_at.desc())
                .limit(6)
            ).all()
        )
        open_tickets = (
            db.scalar(
                select(func.count()).select_from(SupportTicket).where(SupportTicket.status == TicketStatus.OPEN, *ticket_filters)
            )
            or 0
        )

    reports_in_review = 0
    if user_has_feature(user, "reports"):
        reports_count_stmt = (
            select(func.count())
            .select_from(MonthlyReport)
            .join(Case, MonthlyReport.case_id == Case.id)
            .where(MonthlyReport.status == ReportStatus.UNDER_REVIEW)
        )
        reports_in_review = db.scalar(apply_case_scope(reports_count_stmt, user)) or 0

    total_cases_stmt = apply_case_scope(select(func.count()).select_from(Case), user)

    return {
        "open_cases": _count_case_status(CaseStatus.ACTIVE),
        "pending_allotment": _count_case_status(CaseStatus.PENDING_ALLOTMENT),
        "suspended_cases": _count_case_status(CaseStatus.SUSPENDED),
        "closed_cases": _count_case_status(CaseStatus.CLOSED),
        "total_cases": db.scalar(total_cases_stmt) or 0,
        "reports_in_review": reports_in_review,
        "invoices_pending": invoices_pending,
        "open_tickets": open_tickets,
        "status_breakdown": {
            "ACTIVE": _count_case_status(CaseStatus.ACTIVE),
            "PENDING_ALLOTMENT": _count_case_status(CaseStatus.PENDING_ALLOTMENT),
            "SUSPENDED": _count_case_status(CaseStatus.SUSPENDED),
            "CLOSED": _count_case_status(CaseStatus.CLOSED),
        },
        "pending_allotment_queue": [
            {
                "id": row.id,
                "case_code": row.case_code,
                "child_name": f"{row.first_name} {row.last_name}".strip(),
                "service_type": row.service_type,
                "status": row.status.value if hasattr(row.status, "value") else str(row.status),
            }
            for row in pending_rows
        ],
        "reports_queue": [
            {
                "id": row.id,
                "case_id": row.case_id,
                "month": row.month,
                "status": row.status.value if hasattr(row.status, "value") else str(row.status),
                "case_code": row.case_code,
                "child_name": f"{row.first_name} {row.last_name}".strip(),
            }
            for row in report_rows
        ],
        "invoices_queue": [
            {
                "id": inv.id,
                "month": inv.month,
                "amount_inr": float(inv.amount_inr),
                "status": inv.status.value,
                "therapist_user_id": inv.therapist_user_id,
            }
            for inv in invoice_rows
        ],
        "tickets_queue": [
            {
                "id": t.id,
                "subject": t.subject,
                "status": t.status.value,
                "product_module": t.product_module,
            }
            for t in ticket_rows
        ],
    }


@router.get("/sessions/analytics")
def sessions_analytics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    therapist_id: Optional[int] = None,
    product_module: Optional[str] = None,
    session_status: Optional[str] = Query(None, alias="status"),
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    from datetime import date, timedelta
    from sqlalchemy import case as sa_case, cast, String, distinct
    from app.models.session import SessionStatus

    today = date.today()
    d_from = date.fromisoformat(date_from) if date_from else today - timedelta(days=29)
    d_to = date.fromisoformat(date_to) if date_to else today

    allowed_cases = get_allowed_case_product_modules(user)
    base_filters = []
    if allowed_cases is not None:
        base_filters.append(Case.product_module.in_(allowed_cases) if allowed_cases else Case.id == -1)
    if therapist_id:
        base_filters.append(TherapySession.therapist_user_id == therapist_id)
    if product_module:
        base_filters.append(Case.product_module == product_module)
    if session_status:
        base_filters.append(TherapySession.status == session_status)

    # Base join: session → case
    base_q = (
        select(TherapySession)
        .join(Case, TherapySession.case_id == Case.id)
        .where(
            TherapySession.scheduled_date >= d_from,
            TherapySession.scheduled_date <= d_to,
            *base_filters,
        )
    )

    # Today count
    today_count = db.scalar(
        select(func.count())
        .select_from(TherapySession)
        .join(Case, TherapySession.case_id == Case.id)
        .where(TherapySession.scheduled_date == today, *base_filters)
    ) or 0

    # This-week count
    week_start = today - timedelta(days=today.weekday())
    week_count = db.scalar(
        select(func.count())
        .select_from(TherapySession)
        .join(Case, TherapySession.case_id == Case.id)
        .where(TherapySession.scheduled_date >= week_start, TherapySession.scheduled_date <= today, *base_filters)
    ) or 0

    # Status counts
    status_rows = db.execute(
        select(TherapySession.status, func.count().label("n"))
        .join(Case, TherapySession.case_id == Case.id)
        .where(
            TherapySession.scheduled_date >= d_from,
            TherapySession.scheduled_date <= d_to,
            *base_filters,
        )
        .group_by(TherapySession.status)
    ).all()
    status_counts = {row.status.value if hasattr(row.status, "value") else str(row.status): row.n for row in status_rows}

    # By therapist
    therapist_rows = db.execute(
        select(
            TherapySession.therapist_user_id,
            User.full_name,
            func.count().label("total"),
            func.sum(sa_case((TherapySession.status == SessionStatus.COMPLETED, 1), else_=0)).label("completed"),
            func.sum(sa_case((TherapySession.status == SessionStatus.CANCELLED, 1), else_=0)).label("cancelled"),
            func.sum(sa_case((TherapySession.status == SessionStatus.SCHEDULED, 1), else_=0)).label("scheduled"),
        )
        .join(Case, TherapySession.case_id == Case.id)
        .outerjoin(User, TherapySession.therapist_user_id == User.id)
        .where(
            TherapySession.scheduled_date >= d_from,
            TherapySession.scheduled_date <= d_to,
            *base_filters,
        )
        .group_by(TherapySession.therapist_user_id, User.full_name)
        .order_by(func.count().desc())
    ).all()
    by_therapist = [
        {
            "therapist_id": r.therapist_user_id,
            "name": r.full_name or f"Therapist #{r.therapist_user_id}",
            "total": r.total,
            "completed": int(r.completed or 0),
            "cancelled": int(r.cancelled or 0),
            "scheduled": int(r.scheduled or 0),
        }
        for r in therapist_rows
    ]

    # By product module
    product_rows = db.execute(
        select(
            Case.product_module,
            func.count().label("total"),
            func.sum(sa_case((TherapySession.status == SessionStatus.COMPLETED, 1), else_=0)).label("completed"),
            func.sum(sa_case((TherapySession.status == SessionStatus.CANCELLED, 1), else_=0)).label("cancelled"),
        )
        .join(Case, TherapySession.case_id == Case.id)
        .where(
            TherapySession.scheduled_date >= d_from,
            TherapySession.scheduled_date <= d_to,
            *base_filters,
        )
        .group_by(Case.product_module)
        .order_by(func.count().desc())
    ).all()
    by_product = [
        {
            "module": r.product_module or "unknown",
            "total": r.total,
            "completed": int(r.completed or 0),
            "cancelled": int(r.cancelled or 0),
        }
        for r in product_rows
    ]

    # By day (within requested range)
    day_rows = db.execute(
        select(
            TherapySession.scheduled_date,
            func.count().label("total"),
            func.sum(sa_case((TherapySession.status == SessionStatus.COMPLETED, 1), else_=0)).label("completed"),
            func.sum(sa_case((TherapySession.status == SessionStatus.CANCELLED, 1), else_=0)).label("cancelled"),
        )
        .join(Case, TherapySession.case_id == Case.id)
        .where(
            TherapySession.scheduled_date >= d_from,
            TherapySession.scheduled_date <= d_to,
            *base_filters,
        )
        .group_by(TherapySession.scheduled_date)
        .order_by(TherapySession.scheduled_date)
    ).all()
    by_day = [
        {
            "date": r.scheduled_date.isoformat(),
            "total": r.total,
            "completed": int(r.completed or 0),
            "cancelled": int(r.cancelled or 0),
        }
        for r in day_rows
    ]

    # By month (last 12 months from today)
    month_start = (today.replace(day=1) - timedelta(days=365)).replace(day=1)
    from sqlalchemy import extract
    month_rows = db.execute(
        select(
            extract("year", TherapySession.scheduled_date).label("yr"),
            extract("month", TherapySession.scheduled_date).label("mo"),
            func.count().label("total"),
            func.sum(sa_case((TherapySession.status == SessionStatus.COMPLETED, 1), else_=0)).label("completed"),
            func.sum(sa_case((TherapySession.status == SessionStatus.CANCELLED, 1), else_=0)).label("cancelled"),
        )
        .join(Case, TherapySession.case_id == Case.id)
        .where(
            TherapySession.scheduled_date >= month_start,
            *([TherapySession.therapist_user_id == therapist_id] if therapist_id else []),
            *([Case.product_module == product_module] if product_module else []),
            *(base_filters[0:1] if base_filters else []),
        )
        .group_by("yr", "mo")
        .order_by("yr", "mo")
    ).all()
    by_month = [
        {
            "month": f"{int(r.yr)}-{int(r.mo):02d}",
            "total": r.total,
            "completed": int(r.completed or 0),
            "cancelled": int(r.cancelled or 0),
        }
        for r in month_rows
    ]

    # Recent sessions for the table (last 50 within filter range)
    from sqlalchemy.orm import selectinload
    sessions_q = (
        select(TherapySession)
        .join(Case, TherapySession.case_id == Case.id)
        .options(
            selectinload(TherapySession.case).selectinload(Case.child),
        )
        .where(
            TherapySession.scheduled_date >= d_from,
            TherapySession.scheduled_date <= d_to,
            *base_filters,
        )
        .order_by(TherapySession.scheduled_date.desc())
        .limit(50)
    )
    sessions_rows = db.scalars(sessions_q).all()
    recent_sessions = []
    for s in sessions_rows:
        case_obj = s.case
        child_name = (case_obj.child.full_name if case_obj and case_obj.child else None)
        therapist_name = None
        if s.therapist_user_id:
            tu = db.get(User, s.therapist_user_id)
            therapist_name = tu.full_name if tu else None
        duration_mins = None
        if s.actual_start_at and s.actual_end_at:
            duration_mins = int((s.actual_end_at - s.actual_start_at).total_seconds() / 60)
        elif s.start_time and s.end_time:
            from datetime import datetime as dt
            s_start = dt.combine(s.scheduled_date, s.start_time)
            s_end = dt.combine(s.scheduled_date, s.end_time)
            duration_mins = int((s_end - s_start).total_seconds() / 60)
        recent_sessions.append({
            "id": s.id,
            "case_id": s.case_id,
            "case_code": case_obj.case_code if case_obj else None,
            "child_name": child_name,
            "therapist_id": s.therapist_user_id,
            "therapist_name": therapist_name,
            "product_module": case_obj.product_module if case_obj else None,
            "scheduled_date": s.scheduled_date.isoformat(),
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "actual_start_at": s.actual_start_at.isoformat() if s.actual_start_at else None,
            "actual_end_at": s.actual_end_at.isoformat() if s.actual_end_at else None,
            "mode": s.mode.value if hasattr(s.mode, "value") else s.mode,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "duration_mins": duration_mins,
        })

    return {
        "today_count": today_count,
        "week_count": week_count,
        "status_counts": status_counts,
        "by_therapist": by_therapist,
        "by_product": by_product,
        "by_day": by_day,
        "by_month": by_month,
        "recent_sessions": recent_sessions,
        "date_from": d_from.isoformat(),
        "date_to": d_to.isoformat(),
    }


@router.post("/sessions/{session_id}/flag")
def flag_session_for_review(
    session_id: int,
    payload: dict,
    request: Request,
    user: User = Depends(require_permission("case.read.all")),
    db: Session = Depends(get_db),
):
    session = db.get(TherapySession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    case = case_service.get_case(db, session.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Access denied")

    reason = payload.get("reason", "Session flagged for review")
    notes = payload.get("notes", "")
    subject = f"Session #{session_id} flagged: {reason}"
    body = f"Session {session_id} on {session.scheduled_date} was flagged for review.\n\nReason: {reason}"
    if notes:
        body += f"\n\nNotes: {notes}"

    from app.models.support_ticket import TicketCategory, TicketTopic
    ticket = SupportTicket(
        case_id=session.case_id,
        raised_by_user_id=user.id,
        assigned_to_user_id=session.therapist_user_id,
        product_module=case.product_module if case else None,
        category=TicketCategory.SERVICE,
        topic=TicketTopic.THERAPIST,
        subject=subject,
        body=body,
        status=TicketStatus.OPEN,
    )
    db.add(ticket)
    db.flush()
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="flag_session", entity_type="session", entity_id=session_id, **meta)
    db.commit()
    return {"ticket_id": ticket.id, "subject": ticket.subject}


@router.get("/sessions/export/xlsx")
def export_sessions_xlsx(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    therapist_id: Optional[int] = None,
    product_module: Optional[str] = None,
    session_status: Optional[str] = Query(None, alias="status"),
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    import openpyxl
    from datetime import date, timedelta
    from io import BytesIO
    from sqlalchemy import case as sa_case
    from app.models.session import SessionStatus

    today = date.today()
    d_from = date.fromisoformat(date_from) if date_from else today - timedelta(days=29)
    d_to = date.fromisoformat(date_to) if date_to else today
    allowed_cases = get_allowed_case_product_modules(user)
    base_filters = []
    if allowed_cases is not None:
        base_filters.append(Case.product_module.in_(allowed_cases) if allowed_cases else Case.id == -1)
    if therapist_id:
        base_filters.append(TherapySession.therapist_user_id == therapist_id)
    if product_module:
        base_filters.append(Case.product_module == product_module)
    if session_status:
        base_filters.append(TherapySession.status == session_status)

    from sqlalchemy.orm import selectinload
    sessions_rows = db.scalars(
        select(TherapySession)
        .join(Case, TherapySession.case_id == Case.id)
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .where(TherapySession.scheduled_date >= d_from, TherapySession.scheduled_date <= d_to, *base_filters)
        .order_by(TherapySession.scheduled_date.desc())
    ).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sessions"
    headers = ["Session ID", "Date", "Start", "End", "Actual Start", "Actual End", "Duration (min)",
               "Case Code", "Child", "Therapist ID", "Product Module", "Mode", "Status"]
    ws.append(headers)

    for s in sessions_rows:
        case_obj = s.case
        child_name = (case_obj.child.full_name if case_obj and case_obj.child else "")
        duration_mins = ""
        if s.actual_start_at and s.actual_end_at:
            duration_mins = int((s.actual_end_at - s.actual_start_at).total_seconds() / 60)
        elif s.start_time and s.end_time:
            from datetime import datetime as dt
            s_start = dt.combine(s.scheduled_date, s.start_time)
            s_end = dt.combine(s.scheduled_date, s.end_time)
            duration_mins = int((s_end - s_start).total_seconds() / 60)
        ws.append([
            s.id,
            s.scheduled_date.isoformat(),
            s.start_time.isoformat() if s.start_time else "",
            s.end_time.isoformat() if s.end_time else "",
            s.actual_start_at.isoformat() if s.actual_start_at else "",
            s.actual_end_at.isoformat() if s.actual_end_at else "",
            duration_mins,
            case_obj.case_code if case_obj else "",
            child_name,
            s.therapist_user_id,
            case_obj.product_module if case_obj else "",
            s.mode.value if hasattr(s.mode, "value") else str(s.mode),
            s.status.value if hasattr(s.status, "value") else str(s.status),
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=sessions_{d_from}_{d_to}.xlsx"},
    )


@router.get("/sessions/export/pdf")
def export_sessions_pdf(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    therapist_id: Optional[int] = None,
    product_module: Optional[str] = None,
    session_status: Optional[str] = Query(None, alias="status"),
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from datetime import date, timedelta
    from io import BytesIO
    from sqlalchemy.orm import selectinload

    today = date.today()
    d_from = date.fromisoformat(date_from) if date_from else today - timedelta(days=29)
    d_to = date.fromisoformat(date_to) if date_to else today
    allowed_cases = get_allowed_case_product_modules(user)
    base_filters = []
    if allowed_cases is not None:
        base_filters.append(Case.product_module.in_(allowed_cases) if allowed_cases else Case.id == -1)
    if therapist_id:
        base_filters.append(TherapySession.therapist_user_id == therapist_id)
    if product_module:
        base_filters.append(Case.product_module == product_module)
    if session_status:
        base_filters.append(TherapySession.status == session_status)

    sessions_rows = db.scalars(
        select(TherapySession)
        .join(Case, TherapySession.case_id == Case.id)
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .where(TherapySession.scheduled_date >= d_from, TherapySession.scheduled_date <= d_to, *base_filters)
        .order_by(TherapySession.scheduled_date.desc())
        .limit(500)
    ).all()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=30, rightMargin=30, topMargin=40, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph(f"Session Report: {d_from} to {d_to}", styles["Title"]))
    elements.append(Spacer(1, 12))

    table_data = [["Date", "Case", "Child", "Therapist", "Module", "Mode", "Status", "Duration"]]
    for s in sessions_rows:
        c = s.case
        child_name = (c.child.full_name if c and c.child else "")
        duration = ""
        if s.actual_start_at and s.actual_end_at:
            duration = f"{int((s.actual_end_at - s.actual_start_at).total_seconds() / 60)} min"
        elif s.start_time and s.end_time:
            from datetime import datetime as dt
            duration = f"{int((dt.combine(s.scheduled_date, s.end_time) - dt.combine(s.scheduled_date, s.start_time)).total_seconds() / 60)} min"
        table_data.append([
            s.scheduled_date.isoformat(),
            c.case_code if c else "",
            child_name,
            str(s.therapist_user_id),
            c.product_module if c else "",
            s.mode.value if hasattr(s.mode, "value") else str(s.mode),
            s.status.value if hasattr(s.status, "value") else str(s.status),
            duration,
        ])

    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=sessions_{d_from}_{d_to}.pdf"},
    )


@router.get("/session-logs/export")
def export_session_logs(
    therapist_user_id: Optional[int] = None,
    month: Optional[str] = None,
    product_module: Optional[str] = None,
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    logs = log_service.list_logs(db, therapist_user_id=therapist_user_id, month=month, product_module=product_module)
    scoped = []
    for log in logs:
        if not log.session:
            continue
        case = case_service.get_case(db, log.session.case_id)
        if case and case_scope_check(db, user, case):
            scoped.append(log)
    logs = scoped
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "log_id", "session_id", "case_id", "attendance", "session_notes", "activities",
        "goals", "observations", "follow_ups", "parent_notes", "scheduled_date",
        "start_time", "end_time", "actual_start", "actual_end", "submitted_at", "approval_status", "late_addition",
    ])
    for log in logs:
        s = log.session
        writer.writerow([
            log.id,
            log.session_id,
            s.case_id if s else "",
            log.attendance_status,
            log.session_notes or "",
            log.activities_done or "",
            log.goals_addressed or "",
            log.observations or "",
            log.follow_ups or "",
            log.parent_notes or "",
            s.scheduled_date.isoformat() if s else "",
            s.start_time.isoformat() if s and s.start_time else "",
            s.end_time.isoformat() if s and s.end_time else "",
            s.actual_start_at.isoformat() if s and s.actual_start_at else "",
            s.actual_end_at.isoformat() if s and s.actual_end_at else "",
            log.submitted_at.isoformat() if log.submitted_at else "",
            log.approval_status.value,
            log.late_addition,
        ])
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=session_logs.csv"})


def require_user_directory_read(user: User = Depends(get_current_user)) -> User:
    """Staff pickers (tickets, CM meetings) use therapist.read; People uses user.manage."""
    if user_has_permission(user, "user.manage") or user_has_permission(user, "therapist.read"):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to list users")


@router.get("/users", response_model=PaginatedList[UserRead])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_user_directory_read),
    db: Session = Depends(get_db),
):
    stmt = select(User).order_by(User.email)
    users, total = paginate_query(db, stmt, page=page, page_size=page_size)
    items = [
        UserRead(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            phone=u.phone,
            is_active=u.is_active,
            roles=u.role_names,
            region=u.region,
            module_assignments=u.module_assignments or [],
        )
        for u in users
    ]
    return PaginatedList[UserRead](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    current: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.role_names is not None:
        from app.models.role import Role

        roles = db.scalars(select(Role).where(Role.name.in_(payload.role_names))).all()
        target.roles = list(roles)
    if payload.module_assignments is not None:
        target.module_assignments = validate_module_assignments(target.role_names, payload.module_assignments)
    if payload.region is not None:
        target.region = payload.region
    if payload.is_active is not None:
        target.is_active = payload.is_active
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=current.id, action="update", entity_type="user", entity_id=user_id, **meta)
    db.commit()
    db.refresh(target)
    return UserRead(
        id=target.id,
        email=target.email,
        full_name=target.full_name,
        phone=target.phone,
        is_active=target.is_active,
        roles=target.role_names,
        region=target.region,
        module_assignments=target.module_assignments or [],
    )


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    modules = validate_module_assignments(payload.role_names, payload.module_assignments)
    new_user = auth_service.create_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role_names=payload.role_names,
        region=payload.region,
        module_assignments=modules,
    )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="user", entity_id=new_user.id, **meta)
    db.commit()
    db.refresh(new_user)
    return UserRead(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        phone=new_user.phone,
        is_active=new_user.is_active,
        roles=new_user.role_names,
        region=new_user.region,
        module_assignments=new_user.module_assignments or [],
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    request: Request,
    current: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = False
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=current.id, action="deactivate", entity_type="user", entity_id=user_id, **meta)
    db.commit()


@router.post("/therapists/invite")
def invite_therapist(
    payload: InviteCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    """Legacy generic invite; therapist invites use richer metadata via onboard_therapist_invite."""
    role = payload.role_name or "THERAPIST"
    modules = validate_module_assignments([role], payload.module_assignments)
    if role == "THERAPIST":
        try:
            result = therapist_onboard_svc.onboard_therapist_invite(
                db,
                email=payload.email,
                full_name=payload.email.split("@")[0],
                phone=None,
                module_assignments=modules,
                services_offered=[],
                short_bio=None,
                created_by_user_id=user.id,
                send_email=False,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        meta = get_request_meta(request)
        log_audit(
            db,
            actor_user_id=user.id,
            action="invite",
            entity_type="invite_token",
            entity_id=result.get("invite_id"),
            **meta,
        )
        db.commit()
        print(f"[DEV INVITE] {payload.email} -> {result['invite_url']}")
        return {
            "invite_url": result["invite_url"],
            "email": payload.email,
            "expires_at": result["expires_at"],
        }
    token = secrets.token_urlsafe(32)
    invite = InviteToken(
        email=payload.email.lower(),
        role_name=role,
        module_assignments=modules,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_user_id=user.id,
    )
    db.add(invite)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="invite", entity_type="invite_token", entity_id=invite.id, **meta)
    db.commit()
    url = f"{settings.frontend_url}/invite/{token}"
    print(f"[DEV INVITE] {payload.email} -> {url}")
    return {"invite_url": url, "email": payload.email, "expires_at": invite.expires_at.isoformat()}


@router.post("/therapists/onboard")
def onboard_therapist(
    payload: TherapistOnboardCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    validate_module_assignments(["THERAPIST"], payload.module_assignments)
    if payload.services_offered:
        from app.core.therapist_services import validate_service_ids

        try:
            validate_service_ids(payload.services_offered)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        result = therapist_onboard_svc.onboard_therapist(
            db,
            email=str(payload.email),
            full_name=payload.full_name,
            phone=payload.phone,
            module_assignments=payload.module_assignments,
            services_offered=payload.services_offered,
            mode=payload.mode,
            password=payload.password,
            send_email=payload.send_email,
            short_bio=payload.short_bio,
            created_by_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="onboard_therapist", entity_type="user", entity_id=result.get("user_id"), **meta)
    db.commit()
    return result


@router.post("/therapists/bulk-onboard", response_model=list[TherapistOnboardResult])
def bulk_onboard_therapists(
    payload: TherapistBulkOnboardRequest,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.core.therapist_services import validate_service_ids

    rows = []
    for row in payload.therapists:
        validate_module_assignments(["THERAPIST"], row.module_assignments)
        if row.services_offered:
            try:
                validate_service_ids(row.services_offered)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        rows.append(row.model_dump())
    results = therapist_onboard_svc.onboard_therapists_bulk(
        db,
        rows,
        mode=payload.mode,
        send_email=payload.send_email,
        created_by_user_id=user.id,
    )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="bulk_onboard_therapists", entity_type="user", entity_id=None, **meta)
    db.commit()
    return [TherapistOnboardResult(**r) for r in results]


@router.get("/therapist-profiles/summary")
def therapist_profiles_summary(
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.models.role import Role

    profiles = profile_svc.list_profiles(db, None)
    therapists = db.scalars(
        select(User).join(User.roles).where(Role.name == RoleName.THERAPIST.value)
    ).all()
    therapist_ids = {t.id for t in therapists}
    profile_user_ids = {p.user_id for p in profiles}
    counts = {"PENDING": 0, "DRAFT": 0, "APPROVED": 0, "PAUSED": 0}
    for p in profiles:
        key = p.status.value if hasattr(p.status, "value") else str(p.status)
        if key in counts:
            counts[key] += 1
    no_profile = len(therapist_ids - profile_user_ids)
    return {**counts, "no_profile": no_profile, "total": len(profiles)}


@router.get("/therapist-profiles", response_model=list[TherapistProfileRead])
def list_therapist_profiles(
    status: Optional[str] = None,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    st = TherapistProfileStatus(status) if status else None
    profiles = profile_svc.list_profiles(db, st)
    result = []
    for p in profiles:
        u = db.get(User, p.user_id)
        result.append(TherapistProfileRead(**profile_svc.profile_to_dict(p, u)))
    return result


@router.post("/therapist-profiles", response_model=TherapistProfileRead, status_code=status.HTTP_201_CREATED)
def admin_create_therapist_profile(
    payload: TherapistProfileAdminCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, payload.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if RoleName.THERAPIST.value not in target.role_names:
        raise HTTPException(status_code=400, detail="User is not a therapist")
    existing = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == payload.user_id)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists for this therapist")
    profile = TherapistProfile(user_id=payload.user_id)
    profile_svc.apply_profile_fields(profile, payload.model_dump(exclude={"user_id", "status"}))
    try:
        st = TherapistProfileStatus(payload.status or "APPROVED")
    except ValueError:
        st = TherapistProfileStatus.APPROVED
    profile.status = st
    profile.reviewed_by_user_id = user.id
    profile.reviewed_at = datetime.now(timezone.utc)
    db.add(profile)
    db.flush()
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="therapist_profile", entity_id=profile.id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, target))


@router.patch("/therapist-profiles/{profile_id}", response_model=TherapistProfileRead)
def admin_update_therapist_profile(
    profile_id: int,
    payload: TherapistProfileUpdate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile_svc.apply_profile_fields(profile, payload.model_dump(exclude_unset=True))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.commit()
    db.refresh(profile)
    target = db.get(User, profile.user_id)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, target))


@router.get("/therapist-profiles/{user_id}/reviews", response_model=TherapistReviewsResponse)
def admin_therapist_reviews(
    user_id: int,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target or RoleName.THERAPIST.value not in target.role_names:
        raise HTTPException(status_code=404, detail="Therapist not found")
    rows = review_svc.list_therapist_reviews(db, user_id)
    summary = review_svc.review_summary(db, user_id)
    return TherapistReviewsResponse(
        summary=TherapistReviewSummary(**summary),
        reviews=[TherapistSessionReviewRead(**r) for r in rows],
    )


@router.post("/therapist-profiles/{profile_id}/approve", response_model=TherapistProfileRead)
def admin_approve_profile(
    profile_id: int,
    payload: TherapistProfileReview,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.status = TherapistProfileStatus.APPROVED
    profile.reviewed_by_user_id = user.id
    profile.reviewed_at = datetime.now(timezone.utc)
    if payload.admin_note:
        profile.admin_note = payload.admin_note
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="approve_profile", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, db.get(User, profile.user_id)))


@router.post("/therapist-profiles/{profile_id}/pause", response_model=TherapistProfileRead)
def admin_pause_profile(
    profile_id: int,
    payload: TherapistProfileReview,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.status = TherapistProfileStatus.PAUSED
    profile.reviewed_by_user_id = user.id
    profile.reviewed_at = datetime.now(timezone.utc)
    if payload.admin_note:
        profile.admin_note = payload.admin_note
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="pause_profile", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, db.get(User, profile.user_id)))


@router.post("/therapist-profiles/{profile_id}/resume", response_model=TherapistProfileRead)
def admin_resume_profile(
    profile_id: int,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.status = TherapistProfileStatus.APPROVED
    profile.reviewed_by_user_id = user.id
    profile.reviewed_at = datetime.now(timezone.utc)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="resume_profile", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**profile_svc.profile_to_dict(profile, db.get(User, profile.user_id)))


@router.delete("/therapist-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_therapist_profile(
    profile_id: int,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    profile = db.get(TherapistProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="delete", entity_type="therapist_profile", entity_id=profile_id, **meta)
    db.delete(profile)
    db.commit()


# --- Case allotment & families ---


@router.get("/cases/next-code")
def admin_next_case_code(
    product_module: str,
    user: User = Depends(require_permission("case.create")),
    db: Session = Depends(get_db),
):
    from app.services import case_code_service

    code = case_code_service.generate_case_code(db, product_module)
    return {"case_code": code, "preview": case_code_service.preview_case_code(product_module)}


@router.get("/cases/pipeline", response_model=AdminCasePipelineBoard)
def admin_cases_pipeline_board(
    user: User = Depends(_admin_dashboard_user),
    db: Session = Depends(get_db),
):
    """Action-oriented case kanban columns (allotment, reassignment, reports, IEP, compliance)."""
    data = case_pipeline_svc.build_pipeline_board(db, user)
    return AdminCasePipelineBoard(**data)


def _iep_reader(user: User = Depends(get_current_user)) -> User:
    if not (
        user_has_permission(user, "attachment.manage")
        or user_has_permission(user, "iep.read")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user


@router.get("/iep/dashboard", response_model=AdminIepDashboard)
def admin_iep_dashboard(
    status: Optional[str] = Query(None, description="MISSING | INTERNAL_ONLY | AWAITING_ACK | ACKNOWLEDGED | ALL"),
    product_module: Optional[str] = None,
    search: Optional[str] = None,
    include_closed: bool = False,
    user: User = Depends(_iep_reader),
    db: Session = Depends(get_db),
):
    data = admin_iep_svc.build_iep_dashboard(
        db,
        user,
        status=status,
        product_module=product_module,
        search=search,
        include_closed=include_closed,
    )
    return AdminIepDashboard(**data)


@router.get("/allotment/therapists")
def admin_allotment_therapists(
    product_module: str,
    search: Optional[str] = None,
    approved_only: bool = True,
    user: User = Depends(require_permission("case.assign")),
    db: Session = Depends(get_db),
):
    from app.services import allotment_service

    return allotment_service.list_allotment_therapists(db, user, product_module, search, approved_only)


@router.get("/families")
def admin_list_families(
    search: Optional[str] = None,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.services import family_admin_service

    return family_admin_service.list_families(db, search)


@router.post("/children", status_code=status.HTTP_201_CREATED)
def admin_create_child(
    payload: ChildCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.services import family_admin_service

    child = family_admin_service.create_child(
        db, payload.first_name, payload.last_name, payload.date_of_birth
    )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="child", entity_id=child.id, **meta)
    db.commit()
    return {"id": child.id, "fullName": child.full_name}


@router.post("/families", status_code=status.HTTP_201_CREATED)
def admin_create_family(
    payload: FamilyCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.services import family_admin_service

    try:
        result = family_admin_service.create_family(
            db,
            parent_email=payload.parent_email,
            parent_full_name=payload.parent_full_name,
            parent_phone=payload.parent_phone,
            child_first=payload.child.first_name,
            child_last=payload.child.last_name,
            child_dob=payload.child.date_of_birth,
            send_invite=payload.send_invite,
            password=payload.password,
            created_by_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create_family", entity_type="child", entity_id=result["childId"], **meta)
    db.commit()
    if result.get("inviteUrl"):
        print(f"[DEV INVITE] {payload.parent_email} -> {result['inviteUrl']}")
    return result


@router.post("/families/{parent_user_id}/invite")
def admin_invite_parent(
    parent_user_id: int,
    request: Request,
    child_id: Optional[int] = Query(None),
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.services import family_admin_service

    try:
        url = family_admin_service.issue_parent_invite(
            db, parent_user_id, user.id, child_id=child_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="invite", entity_type="user", entity_id=parent_user_id, **meta)
    db.commit()
    return {"invite_url": url}


class StatusRequestReview(BaseModel):
    note: Optional[str] = None


@router.get("/status-requests")
def admin_list_status_requests(
    user: User = Depends(require_permission("case.update")),
    db: Session = Depends(get_db),
):
    from app.services import case_status_request_service as csr_svc

    return csr_svc.list_pending(db)


@router.post("/status-requests/{request_id}/approve")
def admin_approve_status_request(
    request_id: int,
    payload: StatusRequestReview,
    request: Request,
    user: User = Depends(require_permission("case.update")),
    db: Session = Depends(get_db),
):
    from app.services import case_status_request_service as csr_svc

    try:
        case = csr_svc.approve_request(db, request_id, user, payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="approve_status_request",
        entity_type="case_status_request",
        entity_id=request_id,
        case_id=case.id,
        **meta,
    )
    db.commit()
    return {"status": "approved", "caseId": case.case_code}


@router.post("/status-requests/{request_id}/reject")
def admin_reject_status_request(
    request_id: int,
    payload: StatusRequestReview,
    request: Request,
    user: User = Depends(require_permission("case.update")),
    db: Session = Depends(get_db),
):
    from app.services import case_status_request_service as csr_svc

    if not payload.note or len(payload.note.strip()) < 3:
        raise HTTPException(status_code=400, detail="Review note is required to reject")
    try:
        csr_svc.reject_request(db, request_id, user, payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="reject_status_request",
        entity_type="case_status_request",
        entity_id=request_id,
        **meta,
    )
    db.commit()
    return {"status": "rejected"}


@router.get("/observation-checklists")
def admin_list_observation_checklists(
    user: User = Depends(require_permission("monthly_report.approve")),
    db: Session = Depends(get_db),
):
    from app.services import observation_checklist_service as obs_svc

    return obs_svc.list_pending_for_admin(db, user)


@router.get("/observation-checklists/{checklist_id}")
def admin_observation_checklist_detail(
    checklist_id: int,
    user: User = Depends(require_permission("monthly_report.approve")),
    db: Session = Depends(get_db),
):
    from app.models.clinical import ObservationChecklist
    from app.services import case_service, observation_checklist_service as obs_svc

    checklist = db.get(ObservationChecklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    case = case_service.get_case(db, checklist.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return obs_svc.checklist_to_dict(db, checklist, case, user)


@router.post("/observation-checklists/{checklist_id}/approve")
def admin_approve_observation_checklist(
    checklist_id: int,
    payload: ObservationChecklistReview,
    request: Request,
    user: User = Depends(require_permission("monthly_report.approve")),
    db: Session = Depends(get_db),
):
    from app.models.clinical import ObservationChecklist
    from app.schemas.clinical import ObservationChecklistReview
    from app.services import observation_checklist_service as obs_svc

    checklist = db.get(ObservationChecklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    try:
        obs_svc.approve_checklist(
            db,
            checklist,
            user,
            comment=payload.comment,
            share_with_parent=payload.share_with_parent,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="approve_observation_checklist",
        entity_type="observation_checklist",
        entity_id=checklist_id,
        case_id=checklist.case_id,
        **meta,
    )
    db.commit()
    from app.services import case_service

    case = case_service.get_case(db, checklist.case_id)
    return obs_svc.checklist_to_dict(db, checklist, case, user)


@router.post("/observation-checklists/{checklist_id}/reject")
def admin_reject_observation_checklist(
    checklist_id: int,
    payload: ObservationChecklistReview,
    request: Request,
    user: User = Depends(require_permission("monthly_report.approve")),
    db: Session = Depends(get_db),
):
    from app.models.clinical import ObservationChecklist
    from app.schemas.clinical import ObservationChecklistReview
    from app.services import case_service, observation_checklist_service as obs_svc

    checklist = db.get(ObservationChecklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    if not payload.comment or len(payload.comment.strip()) < 3:
        raise HTTPException(status_code=400, detail="Reviewer comment is required")
    try:
        obs_svc.reject_checklist(db, checklist, user, payload.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="reject_observation_checklist",
        entity_type="observation_checklist",
        entity_id=checklist_id,
        case_id=checklist.case_id,
        **meta,
    )
    db.commit()
    case = case_service.get_case(db, checklist.case_id)
    return obs_svc.checklist_to_dict(db, checklist, case, user)


@router.get("/cases/{case_id}/iep-plans")
def admin_list_iep_plans(
    case_id: int,
    user: User = Depends(require_permission("iep.read")),
    db: Session = Depends(get_db),
):
    from app.services import iep_plan_service as iep_svc

    return iep_svc.list_plans_for_case(db, case_id)


@router.get("/cases/{case_id}/iep-plan")
def admin_get_iep_plan(
    case_id: int,
    user: User = Depends(require_permission("iep.read")),
    db: Session = Depends(get_db),
):
    from app.services import case_service, iep_plan_service as iep_svc

    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    plan = iep_svc.get_or_create_plan(db, case, user)
    db.commit()
    return iep_svc.plan_to_dict(db, plan, user)


@router.put("/cases/{case_id}/iep-plan")
def admin_save_iep_plan(
    case_id: int,
    payload: IepPlanSave,
    user: User = Depends(require_permission("iep.read")),
    db: Session = Depends(get_db),
):
    from app.services import case_service, iep_plan_service as iep_svc

    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    plan = iep_svc.get_or_create_plan(db, case, user)
    try:
        iep_svc.save_plan(db, plan, payload.sections, payload.version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return iep_svc.plan_to_dict(db, plan, user)


@router.post("/cases/{case_id}/iep-plan/share-with-parent")
def admin_share_iep_plan(
    case_id: int,
    request: Request,
    user: User = Depends(require_permission("iep.read")),
    db: Session = Depends(get_db),
):
    from app.services import case_service, iep_plan_service as iep_svc

    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    plan = iep_svc.get_or_create_plan(db, case, user)
    try:
        iep_svc.share_plan_with_parent(db, plan, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="share_iep_plan",
        entity_type="iep_plan",
        entity_id=plan.id,
        case_id=case_id,
        **meta,
    )
    db.commit()
    return iep_svc.plan_to_dict(db, plan, user)


@router.post("/families/link-by-email")
def admin_link_parent_by_email(
    child_id: int = Query(...),
    parent_email: str = Query(...),
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.services import family_admin_service

    family_admin_service.link_child_to_parent_by_email(db, child_id, parent_email)
    db.commit()
    return {"status": "linked", "child_id": child_id}


@router.post("/families/link")
def admin_link_parent_child(
    parent_user_id: int = Query(...),
    child_id: int = Query(...),
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    from app.models.parent import ParentGuardian
    from app.models.child import Child

    pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == parent_user_id)).first()
    if not pg:
        pg = ParentGuardian(user_id=parent_user_id)
        db.add(pg)
        db.flush()
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    if child not in pg.children:
        pg.children.append(child)
    from app.services.parent_service import dedupe_parent_child_links

    dedupe_parent_child_links(db, pg.id)
    db.commit()
    return {"status": "linked"}


@router.post("/cases/allot", status_code=status.HTTP_201_CREATED)
def admin_allot_case(
    payload: CaseAllotRequest,
    request: Request,
    user: User = Depends(require_permission("case.create")),
    db: Session = Depends(get_db),
):
    from app.services import allotment_service

    try:
        result = allotment_service.allot_case(db, user, payload.model_dump())
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="allot",
        entity_type="case",
        entity_id=result["case"]["id"],
        **meta,
    )
    db.commit()
    return result


def _reports_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user_has_permission(user, "monthly_report.approve"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if not user_has_feature(user, "reports"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reports module not enabled")
    return user


def _parse_report_status(value: Optional[str]) -> ReportStatus | None:
    if not value:
        return None
    try:
        return ReportStatus(value.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")


@router.get("/reports/summary", response_model=AdminReportSummary)
def admin_reports_summary(
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    return admin_report_svc.get_summary(db, user)


@router.get("/reports/queue", response_model=PaginatedList[AdminReportListItem])
def admin_reports_queue(
    report_type: Optional[str] = Query(None, alias="type"),
    product_module: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    items, meta = admin_report_svc.list_queue_admin(
        db,
        user,
        report_type=report_type,
        product_module=product_module,
        category=category,
        search=search,
        page=page,
        page_size=page_size,
    )
    return PaginatedList[AdminReportListItem](
        items=items,
        total=meta["total"],
        page=meta["page"],
        page_size=meta["page_size"],
        pages=meta["pages"],
    )


@router.get("/reports/monthly", response_model=PaginatedList[AdminReportListItem])
def admin_reports_monthly_list(
    status: Optional[str] = None,
    case_id: Optional[int] = None,
    product_module: Optional[str] = None,
    month: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    parent_review_status: Optional[str] = None,
    queue_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    items, meta = admin_report_svc.list_monthly_admin(
        db,
        user,
        status=_parse_report_status(status),
        case_id=case_id,
        product_module=product_module,
        month=month,
        category=category,
        search=search,
        parent_review_status=parent_review_status,
        queue_only=queue_only,
        page=page,
        page_size=page_size,
    )
    return PaginatedList[AdminReportListItem](
        items=items,
        total=meta["total"],
        page=meta["page"],
        page_size=meta["page_size"],
        pages=meta["pages"],
    )


@router.get("/reports/observation", response_model=PaginatedList[AdminReportListItem])
def admin_reports_observation_list(
    status: Optional[str] = None,
    case_id: Optional[int] = None,
    product_module: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    queue_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    items, meta = admin_report_svc.list_observation_admin(
        db,
        user,
        status=_parse_report_status(status),
        case_id=case_id,
        product_module=product_module,
        category=category,
        search=search,
        queue_only=queue_only,
        page=page,
        page_size=page_size,
    )
    return PaginatedList[AdminReportListItem](
        items=items,
        total=meta["total"],
        page=meta["page"],
        page_size=meta["page_size"],
        pages=meta["pages"],
    )


@router.get("/reports/monthly/{report_id}", response_model=AdminReportDetail)
def admin_reports_monthly_detail(
    report_id: int,
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    detail = admin_report_svc.get_monthly_detail(db, user, report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Report not found")
    return detail


@router.get("/reports/observation/{report_id}", response_model=AdminReportDetail)
def admin_reports_observation_detail(
    report_id: int,
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    detail = admin_report_svc.get_observation_detail(db, user, report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Report not found")
    return detail


@router.post("/reports/monthly/{report_id}/cm-review", response_model=AdminReportDetail)
def admin_reports_monthly_cm_review(
    report_id: int,
    payload: CmReviewAction,
    request: Request,
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    from app.services import case_service, report_service

    report = db.get(MonthlyReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != ReportStatus.UNDER_REVIEW:
        raise HTTPException(status_code=400, detail="Report is not awaiting review")
    if not payload.comment.strip():
        raise HTTPException(status_code=400, detail="Comment is required")
    report_service.cm_review_monthly_report(
        db,
        report,
        user.id,
        comment=payload.comment,
        request_changes=payload.request_changes,
    )
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="cm_review",
        entity_type="monthly_report",
        entity_id=report_id,
        **meta,
    )
    db.commit()
    db.refresh(report)
    detail = admin_report_svc.get_monthly_detail(db, user, report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Report not found")
    return detail


@router.post("/reports/bulk/approve", response_model=BulkReportResult)
def admin_reports_bulk_approve(
    payload: BulkReportAction,
    request: Request,
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    result = admin_report_svc.bulk_approve(
        db,
        user,
        report_type=payload.report_type,
        ids=payload.ids,
        comment=payload.comment,
        visibility=payload.visibility_status,
    )
    meta = get_request_meta(request)
    for rid in payload.ids:
        log_audit(
            db,
            actor_user_id=user.id,
            action="bulk_approve",
            entity_type=f"{payload.report_type}_report",
            entity_id=rid,
            **meta,
        )
    db.commit()
    return result


@router.post("/reports/bulk/reject", response_model=BulkReportResult)
def admin_reports_bulk_reject(
    payload: BulkReportAction,
    request: Request,
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    result = admin_report_svc.bulk_reject(
        db,
        user,
        report_type=payload.report_type,
        ids=payload.ids,
        comment=payload.comment or "",
    )
    meta = get_request_meta(request)
    for rid in payload.ids:
        log_audit(
            db,
            actor_user_id=user.id,
            action="bulk_reject",
            entity_type=f"{payload.report_type}_report",
            entity_id=rid,
            **meta,
        )
    db.commit()
    return result


@router.get("/reports/export/xlsx")
def admin_reports_export_xlsx(
    report_type: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = None,
    case_id: Optional[int] = None,
    product_module: Optional[str] = None,
    month: Optional[str] = None,
    search: Optional[str] = None,
    queue_only: bool = False,
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_report_svc.export_xlsx(
        db,
        user,
        report_type=report_type or "all",
        queue_only=queue_only,
        status=_parse_report_status(status),
        case_id=case_id,
        product_module=product_module,
        month=month,
        search=search,
    )
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="reports-export.xlsx"'},
    )


@router.get("/reports/export/pdf")
def admin_reports_export_pdf(
    report_type: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = None,
    case_id: Optional[int] = None,
    product_module: Optional[str] = None,
    month: Optional[str] = None,
    search: Optional[str] = None,
    queue_only: bool = False,
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    data = admin_report_svc.export_pdf(
        db,
        user,
        report_type=report_type or "all",
        queue_only=queue_only,
        status=_parse_report_status(status),
        case_id=case_id,
        product_module=product_module,
        month=month,
        search=search,
    )
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="reports-export.pdf"'},
    )


@router.get("/reports/missing-monthly")
def admin_reports_missing_monthly(
    month: str = Query(..., description="Month label e.g. May 2026"),
    product_module: Optional[str] = None,
    user: User = Depends(_reports_admin_user),
    db: Session = Depends(get_db),
):
    from app.schemas.report import MissingMonthlyCaseItem

    rows = admin_report_svc.list_missing_monthly(db, user, month=month, product_module=product_module)
    return [MissingMonthlyCaseItem(**r) for r in rows]


@router.get("/invites")
def admin_list_invites(
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(InviteToken)
        .where(InviteToken.used_at.is_(None), InviteToken.expires_at > now)
        .order_by(InviteToken.expires_at.desc())
    ).all()
    return [
        {
            "id": inv.id,
            "email": inv.email,
            "role_name": inv.role_name,
            "module_assignments": inv.module_assignments or [],
            "expires_at": inv.expires_at.isoformat(),
            "invite_url": f"{settings.frontend_url}/invite/{inv.token}",
            "pending_slot_id": (inv.invite_metadata or {}).get("pending_slot_id"),
            "client_name": (inv.invite_metadata or {}).get("client_name"),
            "therapist_user_id": (inv.invite_metadata or {}).get("therapist_user_id"),
        }
        for inv in rows
    ]


@router.post("/invites")
def admin_create_invite(
    payload: InviteCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    return invite_therapist(payload, request, user, db)
