from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.child import Child
from app.models.attachment import Attachment
from app.models.case import Case
from app.models.parent import ParentGuardian, parent_child_link
from app.models.parent_billing import ParentBillingStatement
from app.models.report import MonthlyReport, ReportStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.schemas.parent_profile import ParentProfileRead
from app.services import address_service
from app.services.address_service import user_home_address_read, user_school_address_read

PARENT_VISIBLE = (VisibilityStatus.APPROVED_FOR_PARENT, VisibilityStatus.SHARED_WITH_PARENT)


def _unique_children(children: list[Child]) -> list[Child]:
    seen: set[int] = set()
    out: list[Child] = []
    for child in children:
        if child.id in seen:
            continue
        seen.add(child.id)
        out.append(child)
    return out


def dedupe_parent_child_links(db: Session, parent_guardian_id: int) -> None:
    """Remove duplicate rows in parent_child_links for one guardian."""
    rows = db.execute(
        select(parent_child_link.c.child_id).where(
            parent_child_link.c.parent_guardian_id == parent_guardian_id
        )
    ).all()
    seen: set[int] = set()
    dupes: list[int] = []
    for (child_id,) in rows:
        if child_id in seen:
            dupes.append(child_id)
        else:
            seen.add(child_id)
    for child_id in dupes:
        db.execute(
            delete(parent_child_link).where(
                parent_child_link.c.parent_guardian_id == parent_guardian_id,
                parent_child_link.c.child_id == child_id,
            )
        )


def get_parent_guardian(db: Session, user_id: int) -> ParentGuardian | None:
    return db.scalars(
        select(ParentGuardian)
        .where(ParentGuardian.user_id == user_id)
        .options(selectinload(ParentGuardian.children))
    ).first()


def child_ids_for_parent(db: Session, user_id: int) -> list[int]:
    pg = get_parent_guardian(db, user_id)
    if not pg:
        return []
    return [c.id for c in _unique_children(list(pg.children))]


def primary_parent_user_id_for_child(db: Session, child_id: int) -> int | None:
    pg = db.scalars(
        select(ParentGuardian)
        .join(parent_child_link, ParentGuardian.id == parent_child_link.c.parent_guardian_id)
        .where(parent_child_link.c.child_id == child_id)
    ).first()
    return pg.user_id if pg else None


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
    from app.services.assignment_acceptance_service import (
        active_assignment_for_case,
        parent_has_accepted,
    )

    assignment = active_assignment_for_case(db, case_id)
    if not parent_has_accepted(assignment):
        return None
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


def _batch_active_therapist_names(db: Session, case_ids: list[int]) -> dict[int, str | None]:
    if not case_ids:
        return {}
    subq = (
        select(
            CaseAssignment.case_id,
            func.max(CaseAssignment.id).label("aid"),
        )
        .where(
            CaseAssignment.case_id.in_(case_ids),
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .group_by(CaseAssignment.case_id)
        .subquery()
    )
    rows = db.execute(
        select(CaseAssignment.case_id, User.full_name)
        .join(subq, CaseAssignment.id == subq.c.aid)
        .join(User, User.id == CaseAssignment.therapist_user_id)
    ).all()
    return {int(cid): name for cid, name in rows}


def _batch_case_manager_names(db: Session, cases: list[Case]) -> dict[int, str | None]:
    cm_ids = {c.case_manager_user_id for c in cases if c.case_manager_user_id}
    if not cm_ids:
        return {}
    users = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(cm_ids))).all()}
    return {c.id: users.get(c.case_manager_user_id) for c in cases if c.case_manager_user_id}


def _batch_latest_published_report_month(db: Session, case_ids: list[int]) -> dict[int, str | None]:
    if not case_ids:
        return {}
    subq = (
        select(
            MonthlyReport.case_id,
            func.max(MonthlyReport.id).label("rid"),
        )
        .where(
            MonthlyReport.case_id.in_(case_ids),
            MonthlyReport.visibility_status.in_(PARENT_VISIBLE),
            MonthlyReport.status == ReportStatus.PUBLISHED,
        )
        .group_by(MonthlyReport.case_id)
        .subquery()
    )
    rows = db.execute(
        select(MonthlyReport.case_id, MonthlyReport.month).join(
            subq, MonthlyReport.id == subq.c.rid
        )
    ).all()
    return {int(cid): month for cid, month in rows}


def _batch_iep_status(db: Session, case_ids: list[int]) -> dict[int, str]:
    if not case_ids:
        return {}
    subq = (
        select(Attachment.case_id, func.max(Attachment.id).label("aid"))
        .where(Attachment.case_id.in_(case_ids), Attachment.entity_type == "iep")
        .group_by(Attachment.case_id)
        .subquery()
    )
    rows = db.execute(
        select(Attachment.case_id, Attachment.visibility_status)
        .join(subq, Attachment.id == subq.c.aid)
    ).all()
    out = {cid: "none" for cid in case_ids}
    for case_id, vis in rows:
        if vis == VisibilityStatus.SHARED_WITH_PARENT:
            out[int(case_id)] = "acknowledged"
        else:
            out[int(case_id)] = "pending"
    return out


def _batch_upcoming_booking(db: Session, case_ids: list[int], today: date | None = None) -> dict[int, str | None]:
    from app.services.assignment_acceptance_service import (
        active_assignment_for_case,
        parent_has_accepted,
    )

    today = today or date.today()
    if not case_ids:
        return {}
    eligible_ids = []
    for cid in case_ids:
        if parent_has_accepted(active_assignment_for_case(db, cid)):
            eligible_ids.append(cid)
    if not eligible_ids:
        return {cid: None for cid in case_ids}
    subq = (
        select(
            TherapistSlot.case_id,
            func.min(TherapistSlot.slot_date).label("min_date"),
        )
        .where(
            TherapistSlot.case_id.in_(eligible_ids),
            TherapistSlot.status == SlotStatus.BOOKED,
            TherapistSlot.slot_date >= today,
        )
        .group_by(TherapistSlot.case_id)
        .subquery()
    )
    rows = db.execute(
        select(TherapistSlot.case_id, TherapistSlot.slot_date, TherapistSlot.start_time)
        .join(
            subq,
            (TherapistSlot.case_id == subq.c.case_id) & (TherapistSlot.slot_date == subq.c.min_date),
        )
        .where(
            TherapistSlot.status == SlotStatus.BOOKED,
            TherapistSlot.case_id.in_(eligible_ids),
        )
        .order_by(TherapistSlot.start_time.asc())
    ).all()
    out: dict[int, str | None] = {cid: None for cid in case_ids}
    for case_id, slot_date, start_time in rows:
        cid = int(case_id)
        if cid in out and out[cid] is not None:
            continue
        out[cid] = f"{slot_date} {start_time.strftime('%H:%M')}"
    return out


def parent_case_payload_from_batch(
    case: Case,
    *,
    therapist_name: str | None,
    case_manager_name: str | None,
    latest_month: str | None,
    iep_status: str,
    upcoming_booking: str | None,
) -> dict:
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
        "therapistName": therapist_name,
        "caseManagerName": case_manager_name,
        "latestApprovedReportMonth": latest_month,
        "iepStatus": iep_status,
        "upcomingBooking": upcoming_booking,
    }


def list_parent_cases(db: Session, user: User) -> list[dict]:
    child_ids = child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    cases = db.scalars(
        select(Case).where(Case.child_id.in_(child_ids)).options(selectinload(Case.child))
    ).all()
    case_ids = [c.id for c in cases]
    therapists = _batch_active_therapist_names(db, case_ids)
    cms = _batch_case_manager_names(db, cases)
    months = _batch_latest_published_report_month(db, case_ids)
    iep = _batch_iep_status(db, case_ids)
    bookings = _batch_upcoming_booking(db, case_ids)
    return [
        parent_case_payload_from_batch(
            c,
            therapist_name=therapists.get(c.id),
            case_manager_name=cms.get(c.id),
            latest_month=months.get(c.id),
            iep_status=iep.get(c.id, "none"),
            upcoming_booking=bookings.get(c.id),
        )
        for c in cases
    ]


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


def _profile_children_list(db: Session, user: User, pg: ParentGuardian | None) -> list[dict]:
    """Distinct children from guardian links and active cases (avoids duplicate link inflation)."""
    by_id: dict[int, dict] = {}
    if pg:
        dedupe_parent_child_links(db, pg.id)
        for c in _unique_children(list(pg.children)):
            by_id[c.id] = {
                "id": c.id,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "full_name": c.full_name,
            }
    case_ids = _parent_case_ids_from_user(db, user)
    if case_ids:
        cases = db.scalars(
            select(Case).where(Case.id.in_(case_ids)).options(selectinload(Case.child))
        ).all()
        for case in cases:
            if not case.child:
                continue
            c = case.child
            if c.id not in by_id:
                by_id[c.id] = {
                    "id": c.id,
                    "first_name": c.first_name,
                    "last_name": c.last_name,
                    "full_name": c.full_name,
                }
    return sorted(by_id.values(), key=lambda x: (x["first_name"], x["last_name"]))


def _parent_case_ids_from_user(db: Session, user: User) -> list[int]:
    child_ids = child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    return list(
        db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all()
    )


def add_child_to_parent(db: Session, user: User, first_name: str, last_name: str) -> ParentProfileRead:
    from app.services import family_admin_service

    pg = get_parent_guardian(db, user.id)
    if not pg:
        pg = ParentGuardian(user_id=user.id)
        db.add(pg)
        db.flush()
    child = family_admin_service.create_child(db, first_name.strip(), (last_name or "").strip() or "—")
    linked_ids = {c.id for c in pg.children}
    if child.id not in linked_ids:
        pg.children.append(child)
    db.flush()
    return get_parent_profile(db, user)


def get_parent_profile(db: Session, user: User) -> ParentProfileRead:
    pg = get_parent_guardian(db, user.id)
    children = _profile_children_list(db, user, pg)
    cases_payload = list_parent_cases(db, user)
    services = [
        {
            "case_id": c["id"],
            "case_code": c["caseId"],
            "service_type": c["serviceType"],
            "product_module": c["productModule"],
            "child_name": c["childName"],
        }
        for c in cases_payload
    ]
    homecare_cases = []
    for c in cases_payload:
        if not c.get("isHomecare"):
            continue
        homecare_cases.append(
            {
                "case_id": c["id"],
                "case_code": c["caseId"],
                "child_name": c["childName"],
                "service_address": c.get("serviceAddress"),
                "service_address_summary": c.get("serviceAddressSummary"),
            }
        )
    return ParentProfileRead(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        secondary_contact_name=user.secondary_contact_name,
        secondary_contact_email=user.secondary_contact_email,
        home_address=user_home_address_read(user),
        school_address=user_school_address_read(user),
        address_type=(user.preferred_visit_address_type or "home"),
        children=children,
        services=services,
        homecare_cases=homecare_cases,
    )


def update_parent_profile(db: Session, user: User, payload: dict[str, Any]) -> ParentProfileRead:
    if payload.get("full_name") is not None:
        name = (payload["full_name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        user.full_name = name

    if payload.get("email") is not None:
        requested = str(payload["email"]).strip().lower()
        if requested != (user.email or "").strip().lower():
            raise HTTPException(
                status_code=400,
                detail="Login email cannot be changed from the client portal. Contact support if you need to update it.",
            )

    if "secondary_contact_name" in payload:
        name = payload.get("secondary_contact_name")
        user.secondary_contact_name = name.strip() if name and str(name).strip() else None

    if "secondary_contact_email" in payload:
        email_val = payload.get("secondary_contact_email")
        user.secondary_contact_email = (
            str(email_val).strip().lower() if email_val and str(email_val).strip() else None
        )

    if "phone" in payload:
        phone = payload.get("phone")
        user.phone = phone.strip() if phone and str(phone).strip() else None

    if payload.get("address_type") in ("home", "school"):
        user.preferred_visit_address_type = payload["address_type"]

    home_data = address_service.home_address_from_me_update(payload)
    if home_data:
        address_service.validate_home_address_payload(home_data)
        address_service.apply_home_address_to_user(user, home_data)

    school_data = address_service.school_address_from_parent_update(payload)
    if school_data:
        address_service.validate_school_address_payload(school_data)
        address_service.apply_school_address_to_user(user, school_data)

    child_updates = payload.get("children")
    if child_updates:
        allowed_ids = set(child_ids_for_parent(db, user.id))
        for item in child_updates:
            cid = int(item["id"])
            if cid not in allowed_ids:
                raise HTTPException(status_code=403, detail="Cannot update this child")
            child = db.get(Child, cid)
            if not child:
                raise HTTPException(status_code=404, detail="Child not found")
            child.first_name = item["first_name"].strip()
            child.last_name = item["last_name"].strip()

    svc_patch = payload.get("service_address")
    if svc_patch:
        case_id = int(svc_patch["case_id"])
        case = get_parent_case(db, user, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        if not address_service.is_homecare_case(case):
            raise HTTPException(status_code=400, detail="Service address applies to homecare cases only")
        addr_body = svc_patch.get("address") or {}
        service_data = address_service.service_address_from_payload(addr_body, prefix_keys=False)
        if not service_data:
            service_data = address_service.service_address_from_payload(addr_body, prefix_keys=True)
        if not service_data:
            raise HTTPException(status_code=400, detail="No address fields provided")
        address_service.validate_service_address_payload(service_data, case)
        address_service.apply_service_address_to_case(case, service_data)

    db.flush()
    return get_parent_profile(db, user)
