"""Case Manager dedicated home: caseload + prioritized action queues."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.daily_log import DailyLog
from app.models.incident import Incident, OPEN_INCIDENT_STATUSES
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.user import User
from app.services import admin_case_pipeline_service as pipeline_svc
from app.services import admin_workbench_service as workbench_svc
from app.services.admin_scope_service import apply_case_scope

ACTION_COLUMNS = frozenset(
    {
        "pending_allotment",
        "needs_therapist",
        "reassignment",
        "reports_logs",
        "iep",
        "compliance",
    }
)


def _caseload_target_tab(
    pipeline_column: str,
    *,
    reports_under_review: int,
    missing_logs: int,
) -> str:
    if pipeline_column in ("pending_allotment", "needs_therapist", "reassignment"):
        return "assignments"
    if pipeline_column == "reports_logs":
        return "reports" if reports_under_review > 0 else "logs"
    if pipeline_column == "iep":
        return "iep"
    if pipeline_column == "compliance":
        return "logs" if missing_logs > 0 else "activity"
    return "overview"

SECTION_ORDER = [
    "observations",
    "status_requests",
    "reports",
    "logs",
    "reschedules",
    "tickets",
    "incidents",
    "iep",
    "meetings",
]


def _cm_caseload_stmt(user: User):
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
    stmt = apply_case_scope(stmt, user)
    if user_has_permission(user, "case.read.team") and not user_has_permission(user, "case.read.all"):
        stmt = stmt.where(Case.case_manager_user_id == user.id)
    return stmt


def build_cm_home(db: Session, user: User) -> dict:
    cases = db.scalars(_cm_caseload_stmt(user)).all()
    case_ids = [c.id for c in cases]

    metrics_by_id: dict[int, dict] = {}
    if case_ids:
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
        assign_by_case = {r.case_id: (r.full_name, r.end_date) for r in active_assignments}
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
        from app.models.attachment import Attachment
        from app.models.visibility import VisibilityStatus

        iep_rows = db.scalars(
            select(Attachment).where(Attachment.case_id.in_(case_ids), Attachment.entity_type == "iep")
        ).all()
        iep_by_case: dict[int, Attachment] = {}
        for att in iep_rows:
            prev = iep_by_case.get(att.case_id)
            if not prev or att.created_at > prev.created_at:
                iep_by_case[att.case_id] = att

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
            column = pipeline_svc._classify_pipeline(
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
            metrics_by_id[case.id] = {
                "therapist_name": therapist_name,
                "reports_u": reports_u,
                "missing": missing,
                "tickets": tickets,
                "incidents": incidents,
                "column": column,
                "next_action": pipeline_svc._next_action(
                    column,
                    missing_logs=missing,
                    reports_under_review=reports_u,
                    has_iep=has_iep,
                ),
            }

    caseload_rows = []
    summary = {
        "total": len(cases),
        "active": 0,
        "pending_allotment": 0,
        "needs_action": 0,
        "suspended": 0,
    }
    for case in cases:
        st = case.status.value if hasattr(case.status, "value") else str(case.status)
        if st == CaseStatus.ACTIVE.value:
            summary["active"] += 1
        elif st == CaseStatus.PENDING_ALLOTMENT.value:
            summary["pending_allotment"] += 1
        elif st == CaseStatus.SUSPENDED.value:
            summary["suspended"] += 1

        m = metrics_by_id.get(case.id, {})
        column = m.get("column", "active")
        if column in ACTION_COLUMNS or st == CaseStatus.PENDING_ALLOTMENT.value:
            summary["needs_action"] += 1

        reports_u = m.get("reports_u", 0)
        missing = m.get("missing", 0)
        target_tab = _caseload_target_tab(
            column,
            reports_under_review=reports_u,
            missing_logs=missing,
        )
        caseload_rows.append(
            {
                "id": case.id,
                "case_code": case.case_code,
                "child_name": case.child.full_name if case.child else None,
                "service_type": case.service_type,
                "product_module": case.product_module,
                "status": st,
                "therapist_name": m.get("therapist_name"),
                "pipeline_column": column,
                "next_action": m.get("next_action"),
                "open_reports": reports_u,
                "missing_logs": missing,
                "open_tickets": m.get("tickets", 0),
                "open_incidents": m.get("incidents", 0),
                "href": f"/admin/cases/{case.id}?tab={target_tab}",
            }
        )

    def _needs_action_sort_key(row: dict) -> tuple:
        col = row.get("pipeline_column") or ""
        priority = {
            "pending_allotment": 0,
            "needs_therapist": 1,
            "reassignment": 2,
            "compliance": 3,
            "reports_logs": 4,
            "iep": 5,
            "active": 6,
            "closed": 7,
        }.get(col, 4)
        return (priority, row.get("case_code") or "")

    caseload_rows.sort(key=_needs_action_sort_key)

    wb = workbench_svc.build_workbench_summary(db, user)
    sections: dict = {}
    for key in SECTION_ORDER:
        sec = wb.get("sections", {}).get(key)
        if sec:
            sections[key] = {"count": sec.get("count", 0), "items": sec.get("items", [])}

    quick_actions = [
        {"id": "cases", "label": "My cases", "href": "/admin/cases"},
        {"id": "queues", "label": "Review queues", "href": "/admin/workbench"},
        {"id": "meetings", "label": "CM meetings", "href": "/admin/cm-meetings"},
    ]
    if user_has_permission(user, "case.create"):
        quick_actions.insert(0, {"id": "allot", "label": "Allot new case", "href": "/admin/cases?allot=1"})

    return {
        "role": "CASE_MANAGER",
        "landing_route": "/admin/cm",
        "caseload_summary": summary,
        "caseload": caseload_rows[:50],
        "sections": sections,
        "quick_actions": quick_actions,
    }
