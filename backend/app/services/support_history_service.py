"""Combined support tickets + incidents history for admin reporting."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timezone
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import case_product_module_allowed, get_allowed_case_product_modules
from app.core.permissions import case_scope_check, user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.child import Child
from app.models.incident import Incident, IncidentStatus, normalize_incident_status
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.user import User
from app.services import case_service


def _parse_date_start(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        d = date.fromisoformat(value[:10])
        return datetime.combine(d, time.min, tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_date_end(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        d = date.fromisoformat(value[:10])
        return datetime.combine(d, time.max, tzinfo=timezone.utc)
    except ValueError:
        return None


def _therapist_on_case(db: Session, case_id: int | None) -> tuple[int | None, str | None]:
    if not case_id:
        return None, None
    asg = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.desc())
    ).first()
    if not asg:
        return None, None
    t = db.get(User, asg.therapist_user_id)
    if not t:
        return None, None
    return t.id, t.full_name


def _case_visible(db: Session, user: User, case: Case | None) -> bool:
    if not case:
        return True
    if user_has_permission(user, "admin.override"):
        return True
    if not case_scope_check(db, user, case):
        return False
    if case.product_module and not case_product_module_allowed(user, case.product_module, db):
        return False
    return True


def _ticket_rows(
    db: Session,
    user: User,
    *,
    status: Optional[str],
    product_module: Optional[str],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    therapist_user_id: Optional[int],
    child_id: Optional[int],
) -> list[dict[str, Any]]:
    if not user_has_permission(user, "ticket.manage") and not user_has_permission(user, "admin.override"):
        return []

    stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc())
    if status:
        try:
            stmt = stmt.where(SupportTicket.status == TicketStatus(status))
        except ValueError:
            pass
    if product_module:
        stmt = stmt.where(SupportTicket.product_module == product_module)
    if date_from:
        stmt = stmt.where(SupportTicket.created_at >= date_from)
    if date_to:
        stmt = stmt.where(SupportTicket.created_at <= date_to)

    tickets = db.scalars(stmt).all()
    case_ids = {t.case_id for t in tickets if t.case_id}
    cases_by_id: dict[int, Case] = {}
    if case_ids:
        q = select(Case).where(Case.id.in_(case_ids)).options(selectinload(Case.child))
        cases_by_id = {c.id: c for c in db.scalars(q).all()}

    if child_id:
        tickets = [t for t in tickets if t.case_id and cases_by_id.get(t.case_id) and cases_by_id[t.case_id].child_id == child_id]

    rows: list[dict[str, Any]] = []
    for t in tickets:
        case = cases_by_id.get(t.case_id) if t.case_id else None
        if not _case_visible(db, user, case):
            continue
        t_uid, t_name = _therapist_on_case(db, t.case_id)
        if therapist_user_id and t_uid != therapist_user_id:
            continue
        reporter = db.get(User, t.raised_by_user_id)
        assignee = db.get(User, t.assigned_to_user_id) if t.assigned_to_user_id else None
        closed_at = t.resolved_at.isoformat() if t.resolved_at else None
        if t.status in (TicketStatus.CLOSED, TicketStatus.RESOLVED) and not closed_at:
            closed_at = t.updated_at.isoformat() if t.updated_at else None
        rows.append(
            {
                "record_type": "ticket",
                "id": t.id,
                "case_id": t.case_id,
                "code": f"TCK-{t.id}",
                "subject": t.subject,
                "status": t.status.value,
                "priority": None,
                "client_name": case_service.case_child_display_name(case) if case else None,
                "therapist_name": t_name,
                "reporter_name": reporter.full_name if reporter else None,
                "assignee_name": assignee.full_name if assignee else None,
                "product_module": t.product_module or (case.product_module if case else None),
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "closed_at": closed_at,
            }
        )
    return rows


def _incident_rows(
    db: Session,
    user: User,
    *,
    status: Optional[str],
    product_module: Optional[str],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    therapist_user_id: Optional[int],
    child_id: Optional[int],
) -> list[dict[str, Any]]:
    if not user_has_permission(user, "incident.read_sensitive"):
        return []

    stmt = select(Incident).order_by(Incident.created_at.desc())
    if status:
        try:
            stmt = stmt.where(Incident.status == normalize_incident_status(status))
        except ValueError:
            pass
    if date_from:
        stmt = stmt.where(Incident.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Incident.created_at <= date_to)

    incidents = db.scalars(stmt).all()
    case_ids = {i.case_id for i in incidents if i.case_id}
    cases_by_id: dict[int, Case] = {}
    if case_ids:
        q = select(Case).where(Case.id.in_(case_ids)).options(selectinload(Case.child))
        cases_by_id = {c.id: c for c in db.scalars(q).all()}

    rows: list[dict[str, Any]] = []
    for inc in incidents:
        case = cases_by_id.get(inc.case_id) if inc.case_id else None
        if product_module and case and case.product_module != product_module:
            continue
        if not _case_visible(db, user, case):
            continue
        if child_id and (not case or case.child_id != child_id):
            continue
        t_uid, t_name = _therapist_on_case(db, inc.case_id)
        if therapist_user_id and t_uid != therapist_user_id:
            continue
        st = normalize_incident_status(inc.status).value
        closed_at = None
        if st == IncidentStatus.CLOSED.value:
            closed_at = inc.escalated_at.isoformat() if inc.escalated_at else None
            if not closed_at and inc.last_owner_activity_at:
                closed_at = inc.last_owner_activity_at.isoformat()
        rows.append(
            {
                "record_type": "incident",
                "id": inc.id,
                "case_id": inc.case_id,
                "code": inc.ticket_code or f"INC-{inc.id}",
                "subject": inc.title,
                "status": st,
                "priority": inc.priority,
                "client_name": case_service.case_child_display_name(case) if case else None,
                "therapist_name": t_name,
                "reporter_name": inc.reporter.full_name if inc.reporter else None,
                "assignee_name": inc.assignee.full_name if inc.assignee else None,
                "product_module": case.product_module if case else inc.service_type,
                "created_at": inc.created_at.isoformat() if inc.created_at else None,
                "closed_at": closed_at,
            }
        )
    return rows


def list_support_history(
    db: Session,
    user: User,
    *,
    record_type: str = "all",
    status: Optional[str] = None,
    product_module: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    therapist_user_id: Optional[int] = None,
    child_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    d_from = _parse_date_start(date_from)
    d_to = _parse_date_end(date_to)
    rows: list[dict[str, Any]] = []
    rt = (record_type or "all").lower()
    if rt in ("all", "tickets"):
        rows.extend(
            _ticket_rows(
                db,
                user,
                status=status,
                product_module=product_module,
                date_from=d_from,
                date_to=d_to,
                therapist_user_id=therapist_user_id,
                child_id=child_id,
            )
        )
    if rt in ("all", "incidents"):
        rows.extend(
            _incident_rows(
                db,
                user,
                status=status,
                product_module=product_module,
                date_from=d_from,
                date_to=d_to,
                therapist_user_id=therapist_user_id,
                child_id=child_id,
            )
        )
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": rows[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def export_support_history_csv(
    db: Session,
    user: User,
    *,
    record_type: str = "all",
    status: Optional[str] = None,
    product_module: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    therapist_user_id: Optional[int] = None,
    child_id: Optional[int] = None,
    max_rows: int = 5000,
) -> str:
    data = list_support_history(
        db,
        user,
        record_type=record_type,
        status=status,
        product_module=product_module,
        date_from=date_from,
        date_to=date_to,
        therapist_user_id=therapist_user_id,
        child_id=child_id,
        page=1,
        page_size=max_rows,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "record_type",
            "code",
            "subject",
            "status",
            "priority",
            "client_name",
            "therapist_name",
            "reporter_name",
            "assignee_name",
            "product_module",
            "created_at",
            "closed_at",
        ],
    )
    writer.writeheader()
    for row in data["items"]:
        writer.writerow({k: row.get(k) or "" for k in writer.fieldnames})
    return buf.getvalue()
