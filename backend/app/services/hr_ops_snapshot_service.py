from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.module_access import user_has_feature
from app.core.permissions import user_has_permission
from app.models.case import Case, CaseStatus
from app.models.clinical import ObservationChecklist, ObservationChecklistStatus
from app.models.support_ticket import SupportTicket, TicketStatus
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import EmploymentStatus, User
from app.services import admin_iep_service as iep_svc
from app.services.admin_scope_service import apply_case_scope


def build_hr_ops_snapshot(db: Session, user: User) -> dict:
    """Read-only programme health counts for HR dashboard."""
    active_cases = 0
    pending_allotment = 0
    if user_has_permission(user, "case.read.all") and user_has_feature(user, "cases"):
        active_stmt = apply_case_scope(
            select(func.count()).select_from(Case).where(Case.status == CaseStatus.ACTIVE),
            user,
        )
        active_cases = int(db.scalar(active_stmt) or 0)
        allot_stmt = apply_case_scope(
            select(func.count()).select_from(Case).where(Case.status == CaseStatus.PENDING_ALLOTMENT),
            user,
        )
        pending_allotment = int(db.scalar(allot_stmt) or 0)

    open_tickets = 0
    if user_has_permission(user, "ticket.manage") and user_has_feature(user, "tickets"):
        open_tickets = int(
            db.scalar(select(func.count()).select_from(SupportTicket).where(SupportTicket.status == TicketStatus.OPEN))
            or 0
        )

    therapists_active = 0
    therapists_pending_profile = 0
    if user_has_permission(user, "therapist.read"):
        therapists_active = int(
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.is_active.is_(True), User.employment_status == EmploymentStatus.ACTIVE)
            )
            or 0
        )
        pending_prof_stmt = (
            select(func.count())
            .select_from(TherapistProfile)
            .where(TherapistProfile.status == TherapistProfileStatus.PENDING)
        )
        therapists_pending_profile = int(db.scalar(pending_prof_stmt) or 0)

    iep_missing = 0
    observation_overdue = 0
    if user_has_permission(user, "case.read.all"):
        if user_has_feature(user, "iep"):
            iep_data = iep_svc.build_iep_dashboard(db, user, include_closed=False)
            iep_missing = int(iep_data.get("summary", {}).get("missing", 0))
        today = date.today()
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
        observation_overdue = int(db.scalar(apply_case_scope(overdue_stmt, user)) or 0)

    pending_leave = 0
    if user_has_permission(user, "leave.manage"):
        from app.models.leave import TherapistLeave, LeaveStatus

        pending_leave = int(
            db.scalar(
                select(func.count()).select_from(TherapistLeave).where(TherapistLeave.status == LeaveStatus.PENDING)
            )
            or 0
        )

    return {
        "active_cases": active_cases,
        "pending_allotment": pending_allotment,
        "open_tickets": open_tickets,
        "therapists_active": therapists_active,
        "therapists_pending_profile": therapists_pending_profile,
        "pending_leave": pending_leave,
        "iep_missing": iep_missing,
        "observation_checklists_overdue": observation_overdue,
    }
