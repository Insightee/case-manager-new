from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import get_allowed_case_product_modules
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.attachment import Attachment
from app.models.case import Case, CaseStatus
from app.models.incident import Incident, IncidentStatus
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.user import User
from app.models.visibility import VisibilityStatus

PIPELINE_COLUMNS = [
    ("pending_allotment", "Pending allotment", "slate"),
    ("needs_therapist", "Needs therapist", "warning"),
    ("reassignment", "Reassignment", "warning"),
    ("reports_logs", "Reports & logs", "danger"),
    ("iep", "IEP", "purple"),
    ("compliance", "Compliance", "danger"),
    ("active", "Active", "success"),
    ("closed", "Closed", "muted"),
]


def _case_filters(user: User) -> list:
    allowed = get_allowed_case_product_modules(user)
    if allowed is None:
        return []
    if not allowed:
        return [Case.id < 0]
    return [Case.product_module.in_(allowed)]


def _classify_pipeline(
    *,
    status: CaseStatus,
    has_active_assignment: bool,
    assignment_end_date: date | None,
    reports_under_review: int,
    missing_logs: int,
    has_iep: bool,
    iep_acknowledged: bool,
    open_tickets: int,
    open_incidents: int,
) -> str:
    if status == CaseStatus.CLOSED:
        return "closed"
    if status == CaseStatus.PENDING_ALLOTMENT:
        return "pending_allotment"
    if status == CaseStatus.SUSPENDED or open_tickets or open_incidents:
        return "compliance"
    if status != CaseStatus.ACTIVE:
        return "active"
    if not has_active_assignment:
        return "needs_therapist"
    if assignment_end_date is not None:
        return "reassignment"
    if reports_under_review or missing_logs:
        return "reports_logs"
    if not has_iep or not iep_acknowledged:
        return "iep"
    return "active"


def _next_action(column: str, *, missing_logs: int, reports_under_review: int, has_iep: bool) -> str | None:
    if column == "pending_allotment":
        return "Allot case & assign therapist"
    if column == "needs_therapist":
        return "Assign therapist"
    if column == "reassignment":
        return "Plan handover or extend assignment"
    if column == "reports_logs":
        if reports_under_review:
            return f"{reports_under_review} report(s) to review"
        if missing_logs:
            return f"{missing_logs} session log(s) missing"
        return "Review documentation"
    if column == "iep":
        return "Upload or share IEP" if not has_iep else "Parent acknowledgement pending"
    if column == "compliance":
        return "Review suspension / tickets / incidents"
    return None


def build_pipeline_board(db: Session, user: User) -> dict:
    filters = _case_filters(user)
    cases = db.scalars(
        select(Case).options(selectinload(Case.child)).where(*filters).order_by(Case.case_code)
    ).all()
    if not cases:
        return {"columns": [{"id": c[0], "title": c[1], "tone": c[2], "count": 0, "cases": []} for c in PIPELINE_COLUMNS], "total_cases": 0}

    case_ids = [c.id for c in cases]

    active_assignments = db.execute(
        select(
            CaseAssignment.case_id,
            CaseAssignment.end_date,
            User.full_name,
        )
        .join(User, User.id == CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.case_id.in_(case_ids),
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    assign_by_case: dict[int, tuple[str | None, date | None]] = {}
    for row in active_assignments:
        assign_by_case[row.case_id] = (row.full_name, row.end_date)

    report_counts = dict(
        db.execute(
            select(MonthlyReport.case_id, func.count())
            .where(
                MonthlyReport.case_id.in_(case_ids),
                MonthlyReport.status == ReportStatus.UNDER_REVIEW,
            )
            .group_by(MonthlyReport.case_id)
        ).all()
    )

    from app.models.daily_log import DailyLog

    missing_log_rows = dict(
        db.execute(
            select(TherapySession.case_id, func.count())
            .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id.in_(case_ids),
                TherapySession.status == SessionStatus.COMPLETED,
                DailyLog.id.is_(None),
            )
            .group_by(TherapySession.case_id)
        ).all()
    )

    iep_rows = db.scalars(
        select(Attachment).where(Attachment.case_id.in_(case_ids), Attachment.entity_type == "iep")
    ).all()
    iep_by_case: dict[int, Attachment] = {}
    for att in iep_rows:
        prev = iep_by_case.get(att.case_id)
        if not prev or att.created_at > prev.created_at:
            iep_by_case[att.case_id] = att

    ticket_counts = dict(
        db.execute(
            select(SupportTicket.case_id, func.count())
            .where(
                SupportTicket.case_id.in_(case_ids),
                SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
            )
            .group_by(SupportTicket.case_id)
        ).all()
    )

    incident_counts = dict(
        db.execute(
            select(Incident.case_id, func.count())
            .where(
                Incident.case_id.in_(case_ids),
                Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.INVESTIGATING]),
            )
            .group_by(Incident.case_id)
        ).all()
    )

    buckets: dict[str, list] = {col[0]: [] for col in PIPELINE_COLUMNS}

    for case in cases:
        therapist_name, end_date = assign_by_case.get(case.id, (None, None))
        has_active = case.id in assign_by_case
        reports_u = int(report_counts.get(case.id, 0))
        missing = int(missing_log_rows.get(case.id, 0))
        iep_att = iep_by_case.get(case.id)
        has_iep = iep_att is not None
        iep_ack = bool(iep_att and iep_att.visibility_status == VisibilityStatus.SHARED_WITH_PARENT)
        tickets = int(ticket_counts.get(case.id, 0))
        incidents = int(incident_counts.get(case.id, 0))

        column = _classify_pipeline(
            status=case.status,
            has_active_assignment=has_active,
            assignment_end_date=end_date,
            reports_under_review=reports_u,
            missing_logs=missing,
            has_iep=has_iep,
            iep_acknowledged=iep_ack,
            open_tickets=tickets,
            open_incidents=incidents,
        )

        card = {
            "id": case.id,
            "case_code": case.case_code,
            "child_name": case.child.full_name if case.child else None,
            "service_type": case.service_type,
            "product_module": case.product_module,
            "status": case.status.value,
            "pipeline_column": column,
            "therapist_name": therapist_name,
            "assignment_end_date": end_date.isoformat() if end_date else None,
            "reports_under_review": reports_u,
            "missing_logs": missing,
            "has_iep": has_iep,
            "iep_acknowledged": iep_ack,
            "open_tickets": tickets,
            "open_incidents": incidents,
            "next_action": _next_action(
                column,
                missing_logs=missing,
                reports_under_review=reports_u,
                has_iep=has_iep,
            ),
        }
        buckets[column].append(card)

    columns = [
        {
            "id": col_id,
            "title": title,
            "tone": tone,
            "count": len(buckets[col_id]),
            "cases": buckets[col_id],
        }
        for col_id, title, tone in PIPELINE_COLUMNS
    ]
    return {"columns": columns, "total_cases": len(cases)}
