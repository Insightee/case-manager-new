from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_write import ensure_case_write_access, ensure_product_module_write_access
from app.core.permissions import (
    case_scope_check,
    require_mutation_permission,
    require_permission,
    user_has_permission,
)
from app.models.case import Case, CaseStatus, ClientBillingMode
from app.models.user import User
from app.schemas.case import CaseCreate, CaseRead, CaseUpdate
from app.schemas.pagination import PaginatedList
from app.core.billing_validation import apply_billing_payload
from app.services import address_service, case_code_service, case_service
from app.services import case_status_request_service as csr_svc
from app.services import observation_checklist_service as obs_svc
from app.schemas.clinical import ClinicalProfileUpdate, ObservationChecklistSave
from datetime import date as date_type
from app.models.case_client_status_audit import CaseClientStatusAudit
from app.services import client_status_service
from app.schemas.iep_plan import IepPlanSuggestionCreate

router = APIRouter(prefix="/cases", tags=["cases"])


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
    user: User = Depends(require_mutation_permission("case.create")),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    billing_data = {k: data.pop(k) for k in list(data.keys()) if k in (
        "product_billing_rule_id", "client_billing_mode", "billing_type", "client_rate_per_session_inr",
        "package_session_count", "package_amount_inr", "compensation_mode", "pay_share_amount_inr",
        "therapist_fixed_pay_inr", "billing_notes",
    )}
    service_data = {k: data.pop(k) for k in list(data.keys()) if k in _SERVICE_ADDRESS_KEYS}
    product_module = data.get("product_module", "homecare")
    ensure_product_module_write_access(user, product_module, db)
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
    billing_data = {k: updates.pop(k) for k in list(updates.keys()) if k in (
        "product_billing_rule_id", "client_billing_mode", "billing_type", "client_rate_per_session_inr",
        "package_session_count", "package_amount_inr", "compensation_mode", "pay_share_amount_inr",
        "therapist_fixed_pay_inr", "billing_notes",
    )}
    service_data = {k: updates.pop(k) for k in list(updates.keys()) if k in _SERVICE_ADDRESS_KEYS}
    for k, v in updates.items():
        setattr(case, k, v)
    if service_data:
        address_service.validate_service_address_payload(service_data, case)
        address_service.apply_service_address_to_case(case, service_data)
    apply_billing_payload(case, billing_data, user.id)
    if "status" in updates:
        new_status = case.status.value if hasattr(case.status, "value") else str(case.status)
        old_status_val = old_status.value if hasattr(old_status, "value") else str(old_status)
        if new_status == CaseStatus.CLOSED.value and old_status_val != CaseStatus.CLOSED.value:
            from app.services.case_close_service import (
                apply_case_closed_side_effects,
                assert_no_blocking_invoices_for_close,
            )

            assert_no_blocking_invoices_for_close(db, case.id)
            apply_case_closed_side_effects(db, case)
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
    user: User = Depends(require_mutation_permission("case.update")),
    db: Session = Depends(get_db),
):
    """Admin-direct client status change with audit trail."""
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
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
        new_value={"new_status": payload.new_status, "effective_date": str(payload.effective_date)},
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


class GoalCandidateCreate(BaseModel):
    domain_key: Optional[str] = Field(default=None, max_length=64)
    label: str = Field(min_length=5)
    rationale: Optional[str] = None
    core_domains: Optional[list[str]] = None
    core_environments: Optional[list[str]] = None
    baseline_state: Optional[str] = None
    desired_state: Optional[str] = None
    goal_statement: Optional[str] = None
    source: Optional[str] = None
    source_daily_log_id: Optional[int] = None
    source_session_id: Optional[int] = None


class StrategyCandidateCreate(BaseModel):
    label: str = Field(min_length=3, max_length=255)
    when_to_use: Optional[str] = None
    how_to_use: Optional[str] = None
    avoid: Optional[str] = None
    domain_key: Optional[str] = None
    environment_context: Optional[str] = None
    core_domains: Optional[list[str]] = None
    core_environments: Optional[list[str]] = None
    strategy_steps: Optional[list[str]] = None
    expected_outcome: Optional[str] = None
    source: Optional[str] = None
    linked_goal_card_id: Optional[int] = None
    source_daily_log_id: Optional[int] = None


class RepositoryReviewAction(BaseModel):
    action: str = Field(pattern="^(approve_case|approve_pool|request_edits|merge|reject)$")
    note: Optional[str] = None
    merged_into_id: Optional[int] = None


@router.get("/{case_id}/reports-workbench")
def get_reports_workbench(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import clinical_workbench_service as wb_svc

    case = _case_for_user(db, user, case_id)
    return wb_svc.build_reports_workbench(db, case, user)


@router.get("/{case_id}/clinical-quality-summary")
def get_clinical_quality_summary(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import clinical_workbench_service as wb_svc

    _case_for_user(db, user, case_id)
    return wb_svc.build_clinical_quality_summary(db, case_id)


@router.get("/{case_id}/goal-candidates")
def list_goal_candidates(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goal_repository_service as repo_svc

    _case_for_user(db, user, case_id)
    return {"items": repo_svc.list_goal_candidates(db, case_id)}


@router.get("/{case_id}/goals-engine")
def get_goals_engine(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goals_engine_service as engine_svc

    _case_for_user(db, user, case_id)
    return engine_svc.build_goals_engine_payload(db, case_id)


@router.post("/{case_id}/goal-candidates", status_code=201)
def create_goal_candidate(
    case_id: int,
    payload: GoalCandidateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goal_repository_service as repo_svc

    _case_for_user_write(db, user, case_id)
    domain_key = payload.domain_key or ((payload.core_domains or [None])[0]) or "communication"
    item = repo_svc.create_goal_candidate(
        db,
        case_id=case_id,
        user_id=user.id,
        domain_key=domain_key,
        label=payload.label,
        rationale=payload.rationale,
        source_daily_log_id=payload.source_daily_log_id,
        source_session_id=payload.source_session_id,
        core_domains=payload.core_domains,
        core_environments=payload.core_environments,
        baseline_state=payload.baseline_state,
        desired_state=payload.desired_state,
        goal_statement=payload.goal_statement,
        source=payload.source,
    )
    return item


@router.get("/{case_id}/strategy-candidates")
def list_strategy_candidates(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goal_repository_service as repo_svc

    _case_for_user(db, user, case_id)
    return {"items": repo_svc.list_strategy_candidates(db, case_id)}


@router.post("/{case_id}/strategy-candidates", status_code=201)
def create_strategy_candidate(
    case_id: int,
    payload: StrategyCandidateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goal_repository_service as repo_svc

    _case_for_user_write(db, user, case_id)
    domain_key = payload.domain_key or ((payload.core_domains or [None])[0])
    environment_context = payload.environment_context or ((payload.core_environments or [None])[0])
    item = repo_svc.create_strategy_candidate(
        db,
        case_id=case_id,
        user_id=user.id,
        label=payload.label,
        when_to_use=payload.when_to_use,
        how_to_use=payload.how_to_use,
        avoid=payload.avoid,
        domain_key=domain_key,
        environment_context=environment_context,
        linked_goal_card_id=payload.linked_goal_card_id,
        source_daily_log_id=payload.source_daily_log_id,
        core_domains=payload.core_domains,
        core_environments=payload.core_environments,
        strategy_steps=payload.strategy_steps,
        expected_outcome=payload.expected_outcome,
        source=payload.source,
    )
    return item


@router.get("/{case_id}/repository-review-queue")
def get_repository_review_queue(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goal_repository_service as repo_svc

    _case_for_user(db, user, case_id)
    return repo_svc.list_pending_for_case(db, case_id)


@router.get("/{case_id}/goals/{goal_card_id}/strategy-suggestions")
def get_strategy_suggestions(
    case_id: int,
    goal_card_id: int,
    environment: Optional[str] = Query(None),
    exclude: Optional[str] = Query(None, description="Comma-separated strategy ids to exclude"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import strategy_suggestion_service as sug_svc

    _case_for_user(db, user, case_id)
    exclude_ids = [int(x) for x in (exclude or "").split(",") if x.strip().isdigit()]
    domain_key = None
    from app.models.clinical_evidence import IepGoalCard

    card = db.get(IepGoalCard, goal_card_id)
    if card and card.case_id == case_id:
        domain_key = card.domain_key
    return {
        "items": sug_svc.suggest_alternative_strategies(
            db,
            case_id=case_id,
            goal_card_id=goal_card_id,
            domain_key=domain_key,
            environment=environment,
            exclude_strategy_ids=exclude_ids,
        )
    }


@router.post("/{case_id}/goal-repository/{item_id}/review")
def review_goal_repository_item(
    case_id: int,
    item_id: int,
    payload: RepositoryReviewAction,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goal_repository_service as repo_svc

    _case_for_user_write(db, user, case_id)
    try:
        item = repo_svc.review_goal_item(
            db,
            item_id,
            action=payload.action,
            actor_user_id=user.id,
            note=payload.note,
            merged_into_id=payload.merged_into_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not item:
        raise HTTPException(status_code=404, detail="Goal candidate not found")
    return item


@router.post("/{case_id}/strategy-repository/{item_id}/review")
def review_strategy_repository_item(
    case_id: int,
    item_id: int,
    payload: RepositoryReviewAction,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goal_repository_service as repo_svc

    _case_for_user_write(db, user, case_id)
    try:
        item = repo_svc.review_strategy_item(
            db,
            item_id,
            action=payload.action,
            actor_user_id=user.id,
            note=payload.note,
            merged_into_id=payload.merged_into_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not item:
        raise HTTPException(status_code=404, detail="Strategy candidate not found")
    return item


class LinkEvidencePayload(BaseModel):
    document_id: int
    linked_report_id: Optional[int] = None
    linked_goal_id: Optional[int] = None
    linked_strategy_id: Optional[int] = None
    domain_key: Optional[str] = None


@router.get("/{case_id}/goals/evidence-summary")
def get_goals_evidence_summary(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goal_evidence_aggregation_service as ev_agg

    _case_for_user(db, user, case_id)
    return ev_agg.build_goals_evidence_summary(db, case_id)


@router.get("/{case_id}/strategies/evidence-summary")
def get_strategies_evidence_summary(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import goal_evidence_aggregation_service as ev_agg

    _case_for_user(db, user, case_id)
    return ev_agg.build_strategies_evidence_summary(db, case_id)


@router.get("/{case_id}/iep-review-suggestions")
def list_iep_review_suggestions(
    case_id: int,
    include_resolved: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import iep_review_suggestions_service as iep_rev_svc

    _case_for_user(db, user, case_id)
    return iep_rev_svc.list_suggestions(db, case_id, include_resolved=include_resolved)


@router.post("/{case_id}/iep-review-suggestions/{suggestion_id}/accept")
def accept_iep_review_suggestion(
    case_id: int,
    suggestion_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import iep_review_suggestions_service as iep_rev_svc

    _case_for_user_write(db, user, case_id)
    try:
        result = iep_rev_svc.accept_suggestion(db, case_id, suggestion_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return result


@router.post("/{case_id}/iep-review-suggestions/{suggestion_id}/dismiss")
def dismiss_iep_review_suggestion(
    case_id: int,
    suggestion_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import iep_review_suggestions_service as iep_rev_svc

    _case_for_user_write(db, user, case_id)
    try:
        result = iep_rev_svc.dismiss_suggestion(db, case_id, suggestion_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return result


@router.get("/{case_id}/session-logs/export/pdf")
def export_case_session_logs_pdf(
    case_id: int,
    month: Optional[str] = Query(None, description="Filter by month (YYYY-MM)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import case_session_logs_pdf_service as logs_pdf_svc

    _case_for_user(db, user, case_id)
    if not user_has_permission(user, "session.read") and not user_has_permission(user, "daily_log.create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        pdf_bytes = logs_pdf_svc.build_case_session_logs_pdf(db, user, case_id=case_id, month=month)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    safe_month = (month or "all").replace("-", "")
    filename = f"session_logs_{case_id}_{safe_month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{case_id}/evidence-drive")
def get_evidence_drive(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import evidence_drive_service as drive_svc

    _case_for_user(db, user, case_id)
    return drive_svc.build_evidence_drive(db, user, case_id)


@router.post("/{case_id}/link-evidence")
def link_case_evidence(
    case_id: int,
    payload: LinkEvidencePayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import evidence_drive_service as drive_svc

    _case_for_user_write(db, user, case_id)
    result = drive_svc.link_evidence(
        db,
        user,
        case_id,
        document_id=payload.document_id,
        linked_report_id=payload.linked_report_id,
        linked_goal_id=payload.linked_goal_id,
        linked_strategy_id=payload.linked_strategy_id,
        domain_key=payload.domain_key,
    )
    db.commit()
    return result


@router.get("/{case_id}/reports/monthly/{report_id}/parent-preview")
def case_monthly_parent_preview(
    case_id: int,
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.report import MonthlyReport
    from app.services import parent_safe_report_serializer as parent_safe

    case = _case_for_user(db, user, case_id)
    report = db.get(MonthlyReport, report_id)
    if not report or report.case_id != case.id:
        raise HTTPException(status_code=404, detail="Report not found")
    return parent_safe.serialize_parent_safe_monthly(
        db,
        report,
        case_code=case.case_code,
        child_name=getattr(case, "child_name", "") or "",
    )


@router.post("/{case_id}/iep/ai/review-suggestions")
def generate_iep_ai_review_suggestions(
    case_id: int,
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    from app.services import ai_gateway_service as ai_svc
    from app.services import clinical_insight_summary_service as summary_svc
    from app.services import iep_review_suggestions_service as iep_rev_svc

    _case_for_user_write(db, user, case_id)
    summary = summary_svc.build_monthly_case_summary(db, case_id, month)
    gen = ai_svc.AIGatewayService.suggest_iep_goal_supports(
        db, user_id=user.id, case_id=case_id, summary=summary
    )
    suggestions = []
    for g in gen.get("output", {}).get("goal_recommendations", []):
        suggestions.append(
            iep_rev_svc.create_suggestion_from_ai(
                db,
                case_id=case_id,
                user_id=user.id,
                suggestion_type="continue_goal" if g.get("evidence_strength") != "weak" else "request_evidence",
                reason=g.get("why") or g.get("suggested_next_step") or "",
                goal_title=g.get("goal_title"),
            )
        )
    db.commit()
    return {"items": suggestions, "draft": True, "generated_at": datetime.now(timezone.utc).isoformat()}


@router.post("/{case_id}/goals/{goal_card_id}/ai/suggest-wording")
def suggest_goal_wording(
    case_id: int,
    goal_card_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import ai_gateway_service as ai_svc

    _case_for_user_write(db, user, case_id)
    return ai_svc.AIGatewayService.preview(
        db,
        user_id=user.id,
        case_id=case_id,
        action="suggest_iep_goal_wording",
        context={"goal_card_id": goal_card_id},
        target_type="iep_goal_card",
        target_id=goal_card_id,
    )


@router.post("/{case_id}/strategies/ai/suggest-adaptations")
def suggest_strategy_adaptations(
    case_id: int,
    strategy_label: str = Query(..., min_length=2),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import ai_gateway_service as ai_svc

    _case_for_user_write(db, user, case_id)
    return ai_svc.AIGatewayService.preview(
        db,
        user_id=user.id,
        case_id=case_id,
        action="suggest_strategy_adaptation",
        context={"strategy_label": strategy_label},
        target_type="strategy",
    )
