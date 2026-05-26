from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
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
