from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import case_product_module_allowed
from app.core.permissions import RoleName
from app.models.role import Role
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import User
from app.services import assignment_service, case_code_service, case_service
from app.core.billing_validation import apply_billing_payload
from app.models.case import Case, CaseStatus, ClientBillingMode
from app.services import address_service

_SERVICE_ADDRESS_KEYS = frozenset(
    {
        "service_address_line1",
        "service_address_line2",
        "service_city",
        "service_state",
        "service_pincode",
        "service_landmark",
        "service_latitude",
        "service_longitude",
    }
)


def list_allotment_therapists(
    db: Session,
    actor: User,
    product_module: str,
    search: str | None = None,
    approved_only: bool = True,
) -> list[dict]:
    stmt = (
        select(User)
        .join(User.roles)
        .where(Role.name == RoleName.THERAPIST.value, User.is_active.is_(True))
        .options(selectinload(User.roles))
        .order_by(User.full_name)
    )
    therapists = db.scalars(stmt).unique().all()
    profiles = {
        p.user_id: p
        for p in db.scalars(select(TherapistProfile)).all()
    }
    q = (search or "").strip().lower()
    tokens = [tok for tok in q.split() if tok]
    result = []
    for t in therapists:
        mods = t.module_assignments or []
        if mods and product_module not in mods and not case_product_module_allowed(t, product_module):
            continue
        if approved_only:
            prof = profiles.get(t.id)
            if prof and prof.status != TherapistProfileStatus.APPROVED:
                continue
        if tokens:
            hay = f"{(t.full_name or '').lower()} {(t.email or '').lower()}"
            if not all(tok in hay for tok in tokens):
                continue
        prof = profiles.get(t.id)
        result.append(
            {
                "therapist_user_id": t.id,
                "therapist_name": t.full_name,
                "full_name": t.full_name,
                "email": t.email,
                "profile_status": prof.status.value if prof else None,
            }
        )
    return result


def allot_case(
    db: Session,
    actor: User,
    payload: dict,
) -> dict:
    data = dict(payload)
    therapist_id = data.pop("therapist_user_id")
    start = data.pop("assignment_start_date", None) or date.today()
    reason = data.pop("reason_for_change", "Initial allotment")
    billing_data = {k: data.pop(k) for k in list(data.keys()) if k in (
        "product_billing_rule_id", "billing_type", "client_billing_mode", "client_rate_per_session_inr",
        "package_session_count", "package_amount_inr", "compensation_mode", "pay_share_pct",
        "therapist_fixed_pay_inr", "billing_notes",
    )}
    service_data = {k: data.pop(k) for k in list(data.keys()) if k in _SERVICE_ADDRESS_KEYS}
    client_mode = data.pop("client_billing_mode", None)
    case_code = (data.pop("case_code", None) or "").strip()
    product_module = data["product_module"]
    if not case_code:
        case_code = case_code_service.generate_case_code(db, product_module)
    else:
        case_code_service.ensure_unique_case_code(db, case_code)
    data["case_code"] = case_code
    case = Case(**data)
    if client_mode:
        case.client_billing_mode = ClientBillingMode(client_mode)
    if service_data:
        address_service.validate_service_address_payload(service_data, case)
        address_service.apply_service_address_to_case(case, service_data)
    db.add(case)
    db.flush()
    apply_billing_payload(case, billing_data, actor.id)
    assignment = assignment_service.create_assignment(
        db,
        case_id=case.id,
        therapist_user_id=therapist_id,
        assigned_by_user_id=actor.id,
        start_date=start,
        reason_for_change=reason,
    )
    db.flush()
    return {
        "case": case_service.case_to_read(case, db),
        "assignment_id": assignment.id,
    }


def activate_allotment(
    db: Session,
    actor: User,
    case_id: int,
) -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.assignment import CaseAssignment, CaseAssignmentStatus
    from app.models.child import Child
    from app.models.parent import ParentGuardian, parent_child_link
    from app.services import family_admin_service
    from app.services.email import service as email_service

    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    if case.status not in (CaseStatus.PENDING_ALLOTMENT, CaseStatus.ACTIVE):
        raise ValueError("Case cannot be activated from current status")
    assignment = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.id.desc())
    ).first()
    if not assignment:
        raise ValueError("No active assignment on this case")

    now = datetime.now(timezone.utc)
    case.status = CaseStatus.ACTIVE
    assignment.assignment_offer_sent_at = now
    db.flush()

    parent_invite_urls: list[str] = []
    child = db.get(Child, case.child_id)
    if child:
        parents = db.scalars(
            select(ParentGuardian)
            .join(parent_child_link, ParentGuardian.id == parent_child_link.c.parent_guardian_id)
            .where(parent_child_link.c.child_id == child.id)
            .options(selectinload(ParentGuardian.user))
        ).all()
        for pg in parents:
            if pg.user:
                try:
                    url = family_admin_service.issue_parent_invite(
                        db,
                        pg.user_id,
                        actor.id,
                        child_id=child.id,
                        send_email=True,
                    )
                    parent_invite_urls.append(url)
                except ValueError:
                    pass

    therapist = db.get(User, assignment.therapist_user_id)
    if therapist and therapist.email:
        child_name = child.full_name if child else "the client"
        email_service.send_email(
            to=therapist.email,
            subject=f"New case assignment — {case.case_code}",
            body_text=(
                f"Hello {therapist.full_name or 'there'},\n\n"
                f"You have been assigned to case {case.case_code} ({child_name}). "
                f"Please sign in to your therapist portal to review and accept the assignment.\n\n"
                f"— Insighte"
            ),
        )

    db.flush()
    return {
        "case": case_service.case_to_read(case, db),
        "assignment_id": assignment.id,
        "parent_invite_urls": parent_invite_urls,
    }


def build_allotment_preview(db: Session, case_id: int, *, session_limit: int = 15) -> dict:
    from sqlalchemy import select

    from app.models.assignment import CaseAssignment, CaseAssignmentStatus
    from app.models.session import Session as TherapySession
    from app.models.session import SessionStatus
    from app.models.user import User

    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    assignment = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.id.desc())
    ).first()
    therapist_name = None
    if assignment:
        t = db.get(User, assignment.therapist_user_id)
        therapist_name = t.full_name if t else None

    today = date.today()
    sessions = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.status.in_([SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS]),
            TherapySession.scheduled_date >= today,
        )
        .order_by(TherapySession.scheduled_date.asc(), TherapySession.start_time.asc())
        .limit(session_limit)
    ).all()
    upcoming = [
        {
            "id": s.id,
            "scheduled_date": s.scheduled_date.isoformat(),
            "start_time": s.start_time.strftime("%H:%M") if s.start_time else None,
            "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
            "status": s.status.value,
        }
        for s in sessions
    ]
    case_read = case_service.case_to_read(case, db)
    status_val = case_read.get("status")
    if hasattr(status_val, "value"):
        status_val = status_val.value
    case_read["status"] = status_val
    return {
        "case": case_read,
        "assignment_id": assignment.id if assignment else None,
        "therapist_name": therapist_name,
        "upcoming_sessions": upcoming,
        "billing_summary": {
            "billing_type": case_read.get("billing_type"),
            "client_billing_mode": case_read.get("client_billing_mode"),
            "client_rate_per_session_inr": case_read.get("client_rate_per_session_inr"),
            "package_session_count": case_read.get("package_session_count"),
            "package_amount_inr": case_read.get("package_amount_inr"),
            "pay_share_pct": case_read.get("pay_share_pct"),
        },
    }
