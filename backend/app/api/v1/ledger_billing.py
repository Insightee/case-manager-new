from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.feature_flags import require_billing_ledger_writes
from app.core.module_write import ensure_billing_write_access
from app.core.permissions import require_mutation_permission, require_permission
from app.models.user import User
from app.schemas.ledger_billing import (
    CarePackageAdminCreate,
    CarePackageAdminUpdate,
    GenerateDraftRequest,
    LedgerOverrideRequest,
    OrganisationCreate,
    ProductBillingRuleCreate,
    ProductBillingRuleUpdate,
)
from app.services import (
    billing_ledger_service,
    client_billing_service,
    client_invoice_draft_service,
    product_billing_rule_service,
)
from app.models.client_billing import CarePackage, CarePackageStatus
from app.models.ledger_billing import Organisation
from sqlalchemy import select

router = APIRouter(prefix="/admin/ledger-billing", tags=["ledger-billing"])


def _billing_write(user: User) -> None:
    ensure_billing_write_access(user)


@router.get("/product-rules")
def list_product_rules(
    product_module: Optional[str] = None,
    active_only: bool = True,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return product_billing_rule_service.list_rules(db, active_only=active_only, product_module=product_module)


@router.post("/product-rules", status_code=201)
def create_product_rule(
    payload: ProductBillingRuleCreate,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    _billing_write(user)
    rule = product_billing_rule_service.create_rule(db, payload.model_dump())
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="product_billing_rule", entity_id=rule.id, **meta)
    db.commit()
    return product_billing_rule_service._serialize(rule)


@router.patch("/product-rules/{rule_id}")
def update_product_rule(
    rule_id: int,
    payload: ProductBillingRuleUpdate,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    _billing_write(user)
    rule = product_billing_rule_service.get_rule(db, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    product_billing_rule_service.update_rule(db, rule, payload.model_dump(exclude_unset=True))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="product_billing_rule", entity_id=rule.id, **meta)
    db.commit()
    return product_billing_rule_service._serialize(rule)


@router.get("/ledger")
def list_ledger(
    ledger_month: Optional[str] = None,
    case_id: Optional[int] = None,
    billable_status: Optional[str] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return billing_ledger_service.list_ledger(
        db, ledger_month=ledger_month, case_id=case_id, billable_status=billable_status
    )


@router.patch("/ledger/{ledger_id}")
def override_ledger(
    ledger_id: int,
    payload: LedgerOverrideRequest,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    _billing_write(user)
    try:
        result = billing_ledger_service.override_billable(
            db,
            ledger_id,
            billable_status=payload.billable_status,
            override_reason=payload.override_reason,
            user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="ledger_override", entity_type="billing_ledger", entity_id=ledger_id, **meta)
    db.commit()
    return result


@router.post("/invoices/generate-draft", status_code=201)
def generate_draft(
    payload: GenerateDraftRequest,
    request: Request,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    _billing_write(user)
    try:
        result = client_invoice_draft_service.generate_draft_from_ledger(
            db,
            case_id=payload.case_id,
            billing_month=payload.billing_month,
            actor_user_id=user.id,
            include_pending=payload.include_pending,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="generate_draft",
        entity_type="client_invoice",
        entity_id=result["id"],
        **meta,
    )
    db.commit()
    return result


@router.get("/reconciliation")
def reconciliation(
    case_id: int = Query(...),
    billing_month: str = Query(...),
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return billing_ledger_service.reconcile_month(db, case_id=case_id, billing_month=billing_month)


@router.post("/ensure-period-charges")
def ensure_period_charges(
    request: Request,
    case_id: int = Query(...),
    billing_month: str = Query(..., description="YYYY-MM"),
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """Compute monthly/package period charges for a case-month (idempotent). Staging/finance reconcile."""
    _billing_write(user)
    try:
        result = billing_ledger_service.ensure_period_charges(
            db, case_id=case_id, billing_month=billing_month
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="ensure_period_charges",
        entity_type="case",
        entity_id=case_id,
        new_value={"billing_month": billing_month},
        **meta,
    )
    db.commit()
    return result


@router.post("/ledger/{ledger_id}/post-finance")
def post_finance_charge(
    ledger_id: int,
    request: Request,
    note: Optional[str] = Query(None),
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """Explicit finance post: PENDING_FINANCE → BILLABLE (zero-session DRAFT charges)."""
    _billing_write(user)
    require_billing_ledger_writes()
    try:
        result = billing_ledger_service.post_pending_finance_charge(
            db, ledger_id, user_id=user.id, note=note
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="post_pending_finance",
        entity_type="billing_ledger",
        entity_id=ledger_id,
        **meta,
    )
    db.commit()
    return result


@router.get("/period-flags")
def list_period_flags(
    ledger_month: Optional[str] = None,
    case_id: Optional[int] = None,
    unresolved_only: bool = True,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return billing_ledger_service.list_period_flags(
        db,
        ledger_month=ledger_month,
        case_id=case_id,
        unresolved_only=unresolved_only,
    )


@router.get("/eligibility-exceptions")
def eligibility_exceptions(
    ledger_month: Optional[str] = None,
    case_id: Optional[int] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """Step 5: PENDING_REVIEW log-holds + needs-therapist-confirmation queue (not PENDING_FINANCE)."""
    return billing_ledger_service.eligibility_exceptions_summary(
        db, ledger_month=ledger_month, case_id=case_id
    )


@router.get("/calc-exceptions")
def list_calc_exceptions(
    ledger_month: Optional[str] = None,
    case_id: Optional[int] = None,
    unresolved_only: bool = True,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """Step 6 calculation exceptions (rate gaps, leave credit, missing add-on rate, …)."""
    from app.models.billing_step6 import BillingCalcException

    stmt = select(BillingCalcException).order_by(BillingCalcException.id.desc())
    if ledger_month:
        stmt = stmt.where(BillingCalcException.ledger_month == ledger_month)
    if case_id:
        stmt = stmt.where(BillingCalcException.case_id == case_id)
    if unresolved_only:
        stmt = stmt.where(BillingCalcException.resolved.is_(False))
    rows = db.scalars(stmt.limit(500)).all()
    return [
        {
            "id": r.id,
            "caseId": r.case_id,
            "ledgerMonth": r.ledger_month,
            "code": r.code,
            "message": r.message,
            "sessionId": r.session_id,
            "resolved": r.resolved,
        }
        for r in rows
    ]


@router.post("/cases/{case_id}/client-rate-change")
def apply_client_rate_change(
    case_id: int,
    request: Request,
    new_rate_inr: float = Query(..., gt=0),
    effective_date_choice: str = Query(..., description="START_OF_MONTH | CHANGE_DATE | NEXT_SESSION_ONWARD"),
    billing_month: str = Query(..., description="YYYY-MM"),
    change_date: Optional[str] = Query(None, description="YYYY-MM-DD when choice=CHANGE_DATE"),
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """Step 6 mid-month client rate change — stores choice + resolved_effective_date."""
    from datetime import date as date_cls
    from datetime import datetime, timezone

    from app.models.case import Case
    from app.models.billing_step6 import EffectiveDateChoice
    from app.services import billing_step6_service as step6

    _billing_write(user)
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        choice = EffectiveDateChoice(effective_date_choice)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid effective_date_choice")
    parsed_change = date_cls.fromisoformat(change_date) if change_date else None
    try:
        period = step6.apply_client_rate_change(
            db,
            case=case,
            new_rate_inr=new_rate_inr,
            choice=choice,
            change_date=parsed_change,
            approval_at=datetime.now(timezone.utc),
            billing_month=billing_month,
            actor_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="client_rate_change",
        entity_type="case",
        entity_id=case_id,
        new_value={
            "new_rate_inr": new_rate_inr,
            "effective_date_choice": period.effective_date_choice,
            "resolved_effective_date": (
                period.resolved_effective_date.isoformat() if period.resolved_effective_date else None
            ),
        },
        **meta,
    )
    db.commit()
    return {
        "id": period.id,
        "caseId": period.case_id,
        "startDate": period.start_date.isoformat(),
        "endDate": period.end_date.isoformat() if period.end_date else None,
        "rateInr": float(period.rate_inr),
        "effectiveDateChoice": period.effective_date_choice,
        "resolvedEffectiveDate": (
            period.resolved_effective_date.isoformat() if period.resolved_effective_date else None
        ),
    }


@router.get("/organisations")
def list_organisations(
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    rows = db.scalars(select(Organisation).where(Organisation.active.is_(True)).order_by(Organisation.name)).all()
    return [
        {
            "id": o.id,
            "name": o.name,
            "gstin": o.gstin,
            "billingAddress": o.billing_address,
            "contactEmail": o.contact_email,
            "contactPhone": o.contact_phone,
        }
        for o in rows
    ]


@router.post("/organisations", status_code=201)
def create_organisation(
    payload: OrganisationCreate,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    _billing_write(user)
    org = Organisation(**payload.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return {"id": org.id, "name": org.name, "gstin": org.gstin}


@router.get("/packages")
def admin_list_packages(
    case_id: Optional[int] = None,
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return client_billing_service.admin_list_packages(db, case_id=case_id)


@router.post("/packages", status_code=201)
def admin_create_package(
    payload: CarePackageAdminCreate,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    _billing_write(user)
    try:
        return client_billing_service.admin_create_package(db, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/packages/{package_id}")
def admin_update_package(
    package_id: int,
    payload: CarePackageAdminUpdate,
    user: User = Depends(require_mutation_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    _billing_write(user)
    try:
        return client_billing_service.admin_update_package(db, package_id, payload.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/disputes")
def list_disputes(
    user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    return client_billing_service.admin_list_disputes(db)
