from __future__ import annotations

from datetime import date

from sqlalchemy import and_, case as sa_case, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.services.admin_scope_service import apply_case_scope
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.attachment import Attachment
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.case_therapist_transition import (
    CaseTherapistTransition,
    CaseTherapistTransitionStatus,
)
from app.models.incident import Incident, IncidentStatus, OPEN_INCIDENT_STATUSES
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.parent import ParentGuardian, parent_child_link
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services.assignment_service import (
    resolve_primary_case_manager_user_id,
    sync_case_manager_from_therapist,
)

def pending_therapist_assignment_clause():
    """Cases waiting for a therapist: new allotment or ACTIVE without an active assignment."""
    no_active_assignment = ~exists(
        select(1).where(
            CaseAssignment.case_id == Case.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    )
    return or_(
        Case.status == CaseStatus.PENDING_ALLOTMENT,
        and_(Case.status == CaseStatus.ACTIVE, no_active_assignment),
    )


def count_pending_therapist_assignments(db: Session, user: User) -> int:
    stmt = select(func.count()).select_from(Case).where(pending_therapist_assignment_clause())
    stmt = apply_case_scope(stmt, user)
    return int(db.scalar(stmt) or 0)


def list_pending_therapist_assignment_queue(db: Session, user: User, *, limit: int = 6) -> list[dict]:
    kind_order = sa_case((Case.status == CaseStatus.PENDING_ALLOTMENT, 0), else_=1)
    stmt = (
        select(
            Case.id,
            Case.case_code,
            Case.service_type,
            Case.status,
            Child.first_name,
            Child.last_name,
        )
        .join(Child, Case.child_id == Child.id)
        .where(pending_therapist_assignment_clause())
    )
    stmt = apply_case_scope(stmt, user).order_by(kind_order, Case.created_at.desc()).limit(limit)
    rows = db.execute(stmt).all()
    items: list[dict] = []
    for row in rows:
        status_val = row.status.value if hasattr(row.status, "value") else str(row.status)
        items.append(
            {
                "id": row.id,
                "case_code": row.case_code,
                "child_name": f"{row.first_name} {row.last_name}".strip(),
                "service_type": row.service_type,
                "status": status_val,
                "allotment_kind": "pending_allotment"
                if status_val == CaseStatus.PENDING_ALLOTMENT.value
                else "needs_therapist",
            }
        )
    return items


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
        return "Confirm allotment to activate"
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


def build_pipeline_board(db: Session, user: User) -> tuple[dict, bool]:
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
    stmt = apply_case_scope(stmt, user)
    cases = db.scalars(stmt).all()
    if not cases:
        empty = {
            "columns": [{"id": c[0], "title": c[1], "tone": c[2], "count": 0, "cases": []} for c in PIPELINE_COLUMNS],
            "total_cases": 0,
        }
        return empty, False

    case_ids = [c.id for c in cases]
    child_ids = {c.child_id for c in cases}
    parent_names_by_child: dict[int, str] = {}
    if child_ids:
        for child_id, full_name in db.execute(
            select(parent_child_link.c.child_id, User.full_name)
            .join(ParentGuardian, ParentGuardian.id == parent_child_link.c.parent_guardian_id)
            .join(User, User.id == ParentGuardian.user_id)
            .where(parent_child_link.c.child_id.in_(child_ids))
            .order_by(parent_child_link.c.child_id, ParentGuardian.id)
        ).all():
            if child_id not in parent_names_by_child:
                parent_names_by_child[child_id] = full_name or ""

    active_assignments = db.execute(
        select(
            CaseAssignment.case_id,
            CaseAssignment.end_date,
            CaseAssignment.therapist_user_id,
            User.full_name,
        )
        .join(User, User.id == CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.case_id.in_(case_ids),
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    assign_by_case: dict[int, tuple[int | None, str | None, date | None]] = {}
    for row in active_assignments:
        assign_by_case[row.case_id] = (row.therapist_user_id, row.full_name, row.end_date)

    linked_any = False
    for case in cases:
        if case.case_manager_user_id:
            continue
        therapist_user_id = assign_by_case.get(case.id, (None, None, None))[0]
        if therapist_user_id and sync_case_manager_from_therapist(db, case, therapist_user_id):
            linked_any = True

    cm_ids = {c.case_manager_user_id for c in cases if c.case_manager_user_id}
    cm_names: dict[int, str] = {}
    if cm_ids:
        cm_names = dict(
            db.execute(select(User.id, User.full_name).where(User.id.in_(cm_ids))).all()
        )

    from app.models.therapist_profile import TherapistProfile

    mentored_therapist_ids = set(
        db.scalars(
            select(TherapistProfile.user_id).where(TherapistProfile.mentor_user_id == user.id)
        ).all()
    )

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
                Incident.status.in_(list(OPEN_INCIDENT_STATUSES)),
            )
            .group_by(Incident.case_id)
        ).all()
    )
    transition_case_ids = set(
        db.scalars(
            select(CaseTherapistTransition.case_id)
            .where(
                CaseTherapistTransition.case_id.in_(case_ids),
                CaseTherapistTransition.status.in_(
                    [
                        CaseTherapistTransitionStatus.SCHEDULED,
                        CaseTherapistTransitionStatus.ACTIVE,
                    ]
                ),
            )
            .distinct()
        ).all()
    )

    buckets: dict[str, list] = {col[0]: [] for col in PIPELINE_COLUMNS}

    for case in cases:
        therapist_user_id, therapist_name, end_date = assign_by_case.get(case.id, (None, None, None))
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

        cm_user_id = case.case_manager_user_id
        if not cm_user_id and therapist_user_id:
            cm_user_id = resolve_primary_case_manager_user_id(db, therapist_user_id)

        card = {
            "id": case.id,
            "case_code": case.case_code,
            "child_id": case.child_id,
            "child_name": case.child.full_name if case.child else None,
            "parent_name": parent_names_by_child.get(case.child_id),
            "service_type": case.service_type,
            "product_module": case.product_module,
            "day_type": case.day_type.value if case.day_type else None,
            "in_transition": case.id in transition_case_ids,
            "status": case.status.value,
            "pipeline_column": column,
            "case_manager_user_id": cm_user_id,
            "case_manager_name": cm_names.get(cm_user_id) if cm_user_id else None,
            "is_mentor_case": bool(
                therapist_user_id
                and therapist_user_id in mentored_therapist_ids
                and cm_user_id != user.id
            ),
            "therapist_user_id": therapist_user_id,
            "therapist_name": therapist_name,
            "assignment_end_date": end_date.isoformat() if end_date else None,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "operational_stage": case.operational_stage,
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
    return {"columns": columns, "total_cases": len(cases)}, linked_any
