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
    if case.status == CaseStatus.PENDING_ALLOTMENT:
        case.status = CaseStatus.ACTIVE
    db.flush()
    return {
        "case": case_service.case_to_read(case, db),
        "assignment_id": assignment.id,
    }
