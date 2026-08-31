from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.config import settings
from app.core.database import get_db
from app.core.module_write import (
    ensure_case_transition_allows_write,
    ensure_case_write_access,
    ensure_product_module_write_access,
)
from app.core.permissions import (
    case_scope_check,
    require_any_permission,
    require_mutation_permission,
    require_permission,
    user_has_permission,
)
from app.models.case import Case, CaseStatus, ClientBillingMode
from app.models.user import User
from app.schemas.case import CaseCreate, CaseDayTypeUpdate, CaseRead, CaseUpdate
from app.schemas.billing import CaseBillingFields
from app.schemas.pagination import PaginatedList
from app.services import address_service, billing_approval_service, case_code_service, case_service
from app.services import case_day_type_service
from app.services import case_status_request_service as csr_svc
from app.services import observation_checklist_service as obs_svc
from app.schemas.clinical import ClinicalProfileUpdate, ObservationChecklistSave
from datetime import date as date_type
from app.models.case_client_status_audit import CaseClientStatusAudit
from app.services import client_status_service
from app.schemas.iep_plan import IepPlanSuggestionCreate

router = APIRouter(prefix="/cases", tags=["cases"])


def _apply_case_billing(db: Session, case: Case, billing_data: dict | None, user: User):
    try:
        return billing_approval_service.apply_or_request(
            db,
            case=case,
            proposed=billing_data,
            requester=user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _case_read(db: Session, case: Case, billing_approval=None, *, viewer=None) -> CaseRead:
    result = case_service.case_to_read(case, db, viewer=viewer)
    return CaseRead(**billing_approval_service.stamp_read(result, billing_approval))


class CaseStatusRequestCreate(BaseModel):
    to_status: str = Field(min_length=3, max_length=32)
    reason: str = Field(min_length=5)


class ClientStatusUpdate(BaseModel):
    new_status: str = Field(min_length=2, max_length=32)
    effective_date: date_type
    reason: str = Field(min_length=5)
    internal_notes: Optional[str] = None

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
    search: Optional[str] = Query(None, max_length=128),
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
        search=search,
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
    user: User = Depends(require_mutation_permission("case.create")),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    if "zoho_id" in data:
        data["zoho_id"] = case_service.normalize_zoho_id(data.get("zoho_id"))
    billing_data = {k: data.pop(k) for k in list(data.keys()) if k in (
        "product_billing_rule_id", "client_billing_mode", "billing_type", "client_rate_per_session_inr",
        "client_monthly_rate_inr",
        "package_session_count", "package_amount_inr", "compensation_mode", "pay_share_amount_inr",
        "therapist_fixed_pay_inr", "billing_notes",
        "client_billing_effective_from", "therapist_remuneration_effective_from",
    )}
    service_data = {k: data.pop(k) for k in list(data.keys()) if k in _SERVICE_ADDRESS_KEYS}
    product_module = data.get("product_module", "homecare")
    ensure_product_module_write_access(user, product_module, db)
    day_type_raw = data.pop("day_type", None)
    try:
        data["day_type"] = case_day_type_service.validate_allotment_day_type(product_module, day_type_raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    billing_approval = _apply_case_billing(db, case, billing_data, user)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="case", entity_id=case.id, new_value=payload.model_dump(), **meta)
    if billing_approval:
        log_audit(
            db,
            actor_user_id=user.id,
            action="request_low_margin_billing_approval",
            entity_type="billing_approval_request",
            entity_id=billing_approval.id,
            case_id=case.id,
            old_value=billing_approval.previous_billing,
            new_value={
                "proposed_billing": billing_approval.proposed_billing,
                "projected_profit_inr": float(billing_approval.projected_profit_inr),
            },
            **meta,
        )
    db.commit()
    db.refresh(case)
    return _case_read(db, case, billing_approval, viewer=user)


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    return CaseRead(**case_service.case_to_read(case, db, viewer=user))


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(
    case_id: int,
    payload: CaseUpdate,
    request: Request,
    user: User = Depends(require_mutation_permission("case.update")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    ensure_case_write_access(user, case, db)
    old_status = case.status
    old = {"status": case.status.value, "case_manager_user_id": case.case_manager_user_id}
    updates = payload.model_dump(exclude_unset=True)
    if "zoho_id" in updates:
        updates["zoho_id"] = case_service.normalize_zoho_id(updates.get("zoho_id"))
    billing_data = {k: updates.pop(k) for k in list(updates.keys()) if k in (
        "product_billing_rule_id", "client_billing_mode", "billing_type", "client_rate_per_session_inr",
        "client_monthly_rate_inr",
        "package_session_count", "package_amount_inr", "compensation_mode", "pay_share_amount_inr",
        "therapist_fixed_pay_inr", "billing_notes",
        "client_billing_effective_from", "therapist_remuneration_effective_from",
    )}
    service_data = {k: updates.pop(k) for k in list(updates.keys()) if k in _SERVICE_ADDRESS_KEYS}
    for k, v in updates.items():
        setattr(case, k, v)
    if service_data:
        address_service.validate_service_address_payload(service_data, case)
        address_service.apply_service_address_to_case(case, service_data)
    billing_approval = _apply_case_billing(db, case, billing_data, user)
    if "status" in updates:
        new_status = case.status.value if hasattr(case.status, "value") else str(case.status)
        old_status_val = old_status.value if hasattr(old_status, "value") else str(old_status)
        if new_status == CaseStatus.CLOSED.value and old_status_val != CaseStatus.CLOSED.value:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Closing a case requires a reason and termination date. "
                    "Use POST /api/v1/cases/{id}/client-status with new_status=CLOSED."
                ),
            )
        if (
            old_status_val in (CaseStatus.CLOSED.value, CaseStatus.DEACTIVATED.value)
            and new_status not in (CaseStatus.CLOSED.value, CaseStatus.DEACTIVATED.value)
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Reopening a case requires a reason and reopen date. "
                    "Use POST /api/v1/cases/{id}/client-status."
                ),
            )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="case", entity_id=case.id, old_value=old, new_value=payload.model_dump(exclude_unset=True), **meta)
    if billing_approval:
        log_audit(
            db,
            actor_user_id=user.id,
            action="request_low_margin_billing_approval",
            entity_type="billing_approval_request",
            entity_id=billing_approval.id,
            case_id=case.id,
            old_value=billing_approval.previous_billing,
            new_value={
                "proposed_billing": billing_approval.proposed_billing,
                "projected_profit_inr": float(billing_approval.projected_profit_inr),
            },
            **meta,
        )
    db.commit()
    db.refresh(case)
    return _case_read(db, case, billing_approval, viewer=user)


@router.patch("/{case_id}/billing", response_model=CaseRead)
def update_case_billing(
    case_id: int,
    payload: CaseBillingFields,
    request: Request,
    user: User = Depends(require_any_permission("case.update", "case.billing.update")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    if user.is_view_only:
        raise HTTPException(status_code=403, detail="View-only access — billing changes are not allowed")
    ensure_case_transition_allows_write(case, db)

    proposed = payload.model_dump(exclude_unset=True)
    if not proposed:
        raise HTTPException(status_code=400, detail="Please add the billing details you want to update.")
    previous = billing_approval_service.merged_billing(case, {})
    merged = billing_approval_service.validate_proposed_billing(case, proposed)
    billing_approval = _apply_case_billing(db, case, proposed, user)

    meta = get_request_meta(request)
    action = "request_low_margin_billing_approval" if billing_approval else "update_billing"
    entity_type = "billing_approval_request" if billing_approval else "case"
    entity_id = billing_approval.id if billing_approval else case.id
    log_audit(
        db,
        actor_user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        case_id=case.id,
        old_value=previous,
        new_value={
            "proposed_billing": merged,
            "projected_profit_inr": float(billing_approval_service.projected_profit_inr(merged)),
            "applied": billing_approval is None,
        },
        **meta,
    )
    db.commit()
    db.refresh(case)
    return _case_read(db, case, billing_approval, viewer=user)


@router.patch("/{case_id}/day-type", response_model=CaseRead)
def update_case_day_type(
    case_id: int,
    payload: CaseDayTypeUpdate,
    request: Request,
    user: User = Depends(require_mutation_permission("case.update")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    ensure_case_write_access(user, case, db)
    try:
        case, meta = case_day_type_service.update_case_day_type(
            db,
            case=case,
            actor_user_id=user.id,
            day_type=payload.day_type,
            reason=payload.reason,
            update_billing=payload.update_billing,
            billing_update=payload.billing_update,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if meta.get("changed"):
        audit_meta = get_request_meta(request)
        log_audit(
            db,
            actor_user_id=user.id,
            action="update_day_type",
            entity_type="case",
            entity_id=case.id,
            old_value={"day_type": meta.get("old_day_type")},
            new_value=meta,
            **audit_meta,
        )
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
    ensure_case_write_access(user, case, db)
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


@router.get("/{case_id}/status-requests")
def list_case_status_requests(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    history = csr_svc.list_for_case(db, case_id, limit=10)
    pending = next((h for h in history if h["status"] == "PENDING"), None)
    return {"pending": pending, "history": history}


@router.post("/{case_id}/client-status", status_code=200)
def update_client_status(
    case_id: int,
    payload: ClientStatusUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin/HR client status change with audit trail (close/reopen included)."""
    if not client_status_service.user_can_manage_client_status(user):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    # HR may manage status without full case.update write gates.
    if user_has_permission(user, "case.update"):
        ensure_case_write_access(user, case, db)
    try:
        audit = client_status_service.change_client_status(
            db,
            case=case,
            user=user,
            new_status=payload.new_status,
            effective_date=payload.effective_date,
            reason=payload.reason,
            internal_notes=payload.internal_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="client_status_change",
        entity_type="case",
        entity_id=case.id,
        case_id=case.id,
        new_value={
            "new_status": payload.new_status,
            "effective_date": str(payload.effective_date),
            "reason": payload.reason,
        },
        **meta,
    )
    db.commit()
    db.refresh(case)
    return {
        "case": CaseRead(**case_service.case_to_read(case, db)),
        "auditId": audit.id,
        "message": f"Status updated to {payload.new_status}",
    }


@router.get("/{case_id}/client-status/audit")
def get_client_status_audit(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get client status audit trail for a case."""
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    audit = client_status_service.list_audit_for_case(db, case_id)
    current = case.status.value if hasattr(case.status, "value") else str(case.status)
    return {
        "currentStatus": current,
        "statusEffectiveDate": case.status_effective_date.isoformat() if case.status_effective_date else None,
        "statusReason": case.status_reason,
        "audit": audit,
    }


def _case_for_user(db: Session, user: User, case_id: int) -> Case:
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _case_for_user_write(db: Session, user: User, case_id: int) -> Case:
    case = _case_for_user(db, user, case_id)
    ensure_case_write_access(user, case, db)
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
    case = _case_for_user_write(db, user, case_id)
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
    case = _case_for_user_write(db, user, case_id)
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
    case = _case_for_user_write(db, user, case_id)
    try:
        checklist = obs_svc.submit_checklist(db, case, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return obs_svc.checklist_to_dict(db, checklist, case, user)


@router.get("/{case_id}/iep-plan")
def get_case_iep_plan(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import iep_plan_service as iep_svc

    case = _case_for_user(db, user, case_id)
    plan = iep_svc.get_latest_plan(db, case_id)
    if not plan:
        raise HTTPException(status_code=404, detail="IEP plan not found")
    if settings.enable_structured_evidence:
        goal_items, strategy_items = iep_svc.register_iep_identity_items(db, plan)
        data = iep_svc.plan_to_dict(db, plan, user)
        data["goal_items"] = goal_items
        data["strategy_items"] = strategy_items
        db.commit()
        return data
    return iep_svc.plan_to_dict(db, plan, user)


@router.post("/{case_id}/iep-plan/suggestions")
def case_iep_plan_suggestion(
    case_id: int,
    payload: IepPlanSuggestionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import iep_plan_service as iep_svc

    case = _case_for_user_write(db, user, case_id)
    plan = iep_svc.get_latest_plan(db, case_id)
    if not plan:
        raise HTTPException(status_code=404, detail="IEP plan not found")
    role = user.role_names[0] if user.role_names else "THERAPIST"
    try:
        iep_svc.add_suggestion(db, plan, user, role, payload.body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return iep_svc.plan_to_dict(db, plan, user)


@router.get("/{case_id}/session-logs/export/xlsx")
def export_case_session_logs_xlsx(
    case_id: int,
    view_mode: str = Query("all", pattern="^(month|day|all)$"),
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    day: Optional[str] = Query(None, alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    year: Optional[str] = Query(None, pattern=r"^\d{4}$"),
    status_filter: Optional[str] = Query(None, alias="status"),
    include_content: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi.responses import Response

    from app.services import case_session_log_export_service as export_svc

    _case_for_user(db, user, case_id)
    try:
        content, filename = export_svc.export_staff_case_session_logs_xlsx(
            db,
            case_id=case_id,
            user=user,
            view_mode=view_mode,
            month=month,
            day=day,
            year=year,
            status_filter=status_filter,
            include_content=include_content,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
