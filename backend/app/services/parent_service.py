from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.attachment import Attachment
from app.models.case import Case
from app.models.parent import ParentGuardian
from app.models.parent_billing import ParentBillingStatement
from app.models.report import MonthlyReport, ReportStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services import address_service

PARENT_VISIBLE = (VisibilityStatus.APPROVED_FOR_PARENT, VisibilityStatus.SHARED_WITH_PARENT)


def child_ids_for_parent(db: Session, user_id: int) -> list[int]:
    pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == user_id)).first()
    if not pg:
        return []
    return [c.id for c in pg.children]


def active_therapist_name(db: Session, case_id: int) -> str | None:
    row = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.desc())
    ).first()
    if not row:
        return None
    u = db.get(User, row.therapist_user_id)
    return u.full_name if u else None


def case_manager_name(db: Session, case: Case) -> str | None:
    if not case.case_manager_user_id:
        return None
    u = db.get(User, case.case_manager_user_id)
    return u.full_name if u else None


def latest_published_report_month(db: Session, case_id: int) -> str | None:
    report = db.scalars(
        select(MonthlyReport)
        .where(
            MonthlyReport.case_id == case_id,
            MonthlyReport.visibility_status.in_(PARENT_VISIBLE),
            MonthlyReport.status == ReportStatus.PUBLISHED,
        )
        .order_by(MonthlyReport.created_at.desc())
    ).first()
    return report.month if report else None


def iep_status_for_case(db: Session, case_id: int) -> str:
    att = db.scalars(
        select(Attachment)
        .where(
            Attachment.case_id == case_id,
            Attachment.entity_type == "iep",
            Attachment.visibility_status.in_(PARENT_VISIBLE),
        )
        .order_by(Attachment.created_at.desc())
    ).first()
    if not att:
        return "none"
    if att.visibility_status == VisibilityStatus.SHARED_WITH_PARENT:
        return "acknowledged"
    return "pending"


def upcoming_booking_summary(db: Session, case_id: int, today: date | None = None) -> str | None:
    today = today or date.today()
    slot = db.scalars(
        select(TherapistSlot)
        .where(
            TherapistSlot.case_id == case_id,
            TherapistSlot.status == SlotStatus.BOOKED,
            TherapistSlot.slot_date >= today,
        )
        .order_by(TherapistSlot.slot_date.asc(), TherapistSlot.start_time.asc())
    ).first()
    if not slot:
        return None
    return f"{slot.slot_date} {slot.start_time.strftime('%H:%M')}"


def parent_case_payload(db: Session, case: Case) -> dict:
    svc = address_service.case_service_address_read(case)
    return {
        "id": case.id,
        "caseId": case.case_code,
        "childName": case.child.full_name if case.child else "",
        "serviceType": case.service_type,
        "productModule": case.product_module,
        "status": case.status.value,
        "serviceAddressSummary": address_service.service_address_summary(case),
        "serviceAddress": svc.model_dump() if svc else None,
        "isHomecare": address_service.is_homecare_case(case),
        "therapistName": active_therapist_name(db, case.id),
        "caseManagerName": case_manager_name(db, case),
        "latestApprovedReportMonth": latest_published_report_month(db, case.id),
        "iepStatus": iep_status_for_case(db, case.id),
        "upcomingBooking": upcoming_booking_summary(db, case.id),
    }


def list_parent_cases(db: Session, user: User) -> list[dict]:
    child_ids = child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    cases = db.scalars(
        select(Case).where(Case.child_id.in_(child_ids)).options(selectinload(Case.child))
    ).all()
    return [parent_case_payload(db, c) for c in cases]


def get_parent_case(db: Session, user: User, case_id: int) -> Case | None:
    child_ids = child_ids_for_parent(db, user.id)
    case = db.get(Case, case_id)
    if not case or case.child_id not in child_ids:
        return None
    return case


def list_billing_summaries(db: Session, user: User) -> list[dict]:
    rows = db.scalars(
        select(ParentBillingStatement)
        .where(ParentBillingStatement.parent_user_id == user.id)
        .order_by(ParentBillingStatement.created_at.desc())
    ).all()
    result = []
    for row in rows:
        case_code = None
        child_name = None
        if row.case_id:
            c = db.get(Case, row.case_id)
            if c:
                case_code = c.case_code
                child_name = c.child.full_name if c.child else None
        result.append(
            {
                "id": str(row.id),
                "caseId": case_code,
                "childName": child_name,
                "month": row.month,
                "amountInr": row.amount_inr,
                "status": row.status.value.lower(),
                "detail": row.detail or "",
            }
        )
    return result
