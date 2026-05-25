from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import case_scope_check, require_permission, user_has_permission
from app.models.case import Case, CaseStatus, ClientBillingMode
from app.models.user import User
from app.schemas.case import CaseCreate, CaseRead, CaseUpdate
from app.schemas.pagination import PaginatedList
from app.core.billing_validation import apply_billing_payload
from app.services import address_service, case_code_service, case_service
from app.services import case_status_request_service as csr_svc
from app.services import observation_checklist_service as obs_svc
from app.schemas.clinical import ClinicalProfileUpdate, ObservationChecklistSave

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseStatusRequestCreate(BaseModel):
    to_status: str = Field(min_length=3, max_length=32)
    reason: str = Field(min_length=5)

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


@router.get("", response_model=PaginatedList[CaseRead])
def list_cases(
    assigned: bool = Query(False),
    status: Optional[CaseStatus] = None,
    product_module: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if assigned and not user_has_permission(user, "case.read.assigned"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if not assigned and not (
        user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "case.read.scoped")
    ):
        if not user_has_permission(user, "case.read.assigned"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    data = case_service.list_cases_for_user(
        db,
        user,
        assigned_only=assigned,
        status=status,
        product_module=product_module,
        page=page,
        page_size=page_size,
    )
    return PaginatedList[CaseRead](
        items=[CaseRead(**item) for item in data["items"]],
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
        pages=data["pages"],
    )


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    request: Request,
    user: User = Depends(require_permission("case.create")),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    billing_data = {k: data.pop(k) for k in list(data.keys()) if k in (
        "client_billing_mode", "billing_type", "client_rate_per_session_inr", "package_session_count",
        "package_amount_inr", "compensation_mode", "pay_share_pct",
        "therapist_fixed_pay_inr", "billing_notes",
    )}
    service_data = {k: data.pop(k) for k in list(data.keys()) if k in _SERVICE_ADDRESS_KEYS}
    product_module = data.get("product_module", "homecare")
    case_code = (data.get("case_code") or "").strip()
    if not case_code:
        data["case_code"] = case_code_service.generate_case_code(db, product_module)
    else:
        case_code_service.ensure_unique_case_code(db, case_code)
    if not billing_data.get("client_billing_mode"):
        bt = billing_data.get("billing_type")
        if bt == "PACKAGE":
            billing_data["client_billing_mode"] = ClientBillingMode.PREPAID.value
        elif bt == "PER_SESSION":
            billing_data["client_billing_mode"] = ClientBillingMode.POSTPAID.value
    case = Case(**data)
    if service_data:
        address_service.validate_service_address_payload(service_data, case)
        address_service.apply_service_address_to_case(case, service_data)
    db.add(case)
    db.flush()
    apply_billing_payload(case, billing_data, user.id)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="case", entity_id=case.id, new_value=payload.model_dump(), **meta)
    db.commit()
    db.refresh(case)
    return CaseRead(**case_service.case_to_read(case, db))


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    return CaseRead(**case_service.case_to_read(case, db))


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(
    case_id: int,
    payload: CaseUpdate,
    request: Request,
    user: User = Depends(require_permission("case.update")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    old = {"status": case.status.value, "case_manager_user_id": case.case_manager_user_id}
    updates = payload.model_dump(exclude_unset=True)
    billing_data = {k: updates.pop(k) for k in list(updates.keys()) if k in (
        "client_billing_mode", "billing_type", "client_rate_per_session_inr", "package_session_count",
        "package_amount_inr", "compensation_mode", "pay_share_pct",
        "therapist_fixed_pay_inr", "billing_notes",
    )}
    service_data = {k: updates.pop(k) for k in list(updates.keys()) if k in _SERVICE_ADDRESS_KEYS}
    for k, v in updates.items():
        setattr(case, k, v)
    if service_data:
        address_service.validate_service_address_payload(service_data, case)
        address_service.apply_service_address_to_case(case, service_data)
    apply_billing_payload(case, billing_data, user.id)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="case", entity_id=case.id, old_value=old, new_value=payload.model_dump(exclude_unset=True), **meta)
    db.commit()
    db.refresh(case)
    return CaseRead(**case_service.case_to_read(case, db))


@router.post("/{case_id}/status-requests", status_code=201)
def create_case_status_request(
    case_id: int,
    payload: CaseStatusRequestCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    try:
        req = csr_svc.create_request(db, user, case, payload.to_status, payload.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="status_request",
        entity_type="case_status_request",
        entity_id=req.id,
        case_id=case_id,
        **meta,
    )
    db.commit()
    return {
        "id": req.id,
        "fromStatus": req.from_status,
        "toStatus": req.to_status,
        "status": req.status.value.lower(),
    }


def _case_for_user(db: Session, user: User, case_id: int) -> Case:
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("/{case_id}/clinical-profile")
def get_clinical_profile(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = _case_for_user(db, user, case_id)
    profile = obs_svc.get_or_create_profile(db, case.id)
    return obs_svc.profile_to_dict(profile)


@router.patch("/{case_id}/clinical-profile")
def update_clinical_profile(
    case_id: int,
    payload: ClinicalProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = _case_for_user(db, user, case_id)
    profile = obs_svc.update_profile(db, case, user, payload.model_dump(exclude_unset=True))
    db.commit()
    return obs_svc.profile_to_dict(profile)


@router.get("/{case_id}/observation-checklist")
def get_observation_checklist(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = _case_for_user(db, user, case_id)
    checklist = obs_svc.get_or_create_checklist(db, case, user.id)
    return obs_svc.checklist_to_dict(db, checklist, case, user)


@router.put("/{case_id}/observation-checklist")
def save_observation_checklist(
    case_id: int,
    payload: ObservationChecklistSave,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = _case_for_user(db, user, case_id)
    try:
        checklist = obs_svc.save_checklist(
            db,
            case,
            user,
            payload.responses,
            sync_clinical_profile=payload.sync_clinical_profile,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return obs_svc.checklist_to_dict(db, checklist, case, user)


@router.post("/{case_id}/observation-checklist/submit", status_code=200)
def submit_observation_checklist(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = _case_for_user(db, user, case_id)
    try:
        checklist = obs_svc.submit_checklist(db, case, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return obs_svc.checklist_to_dict(db, checklist, case, user)
