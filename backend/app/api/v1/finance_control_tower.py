"""Stage 1 Finance Control Tower — GET-only, zero side effects."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.feature_flags import require_finance_control_tower_read
from app.models.user import User
from app.services import billing_readiness_master_sheet_service as master_sheet
from app.services import finance_control_tower_service as tower

router = APIRouter(
    prefix="/admin/finance-control-tower",
    tags=["finance-control-tower"],
)


@router.get("/summary")
def control_tower_summary(
    billing_month: Optional[str] = Query(None, description="YYYY-MM"),
    user: User = Depends(require_finance_control_tower_read()),
    db: Session = Depends(get_db),
):
    _ = user
    return tower.control_tower_summary(db, billing_month=billing_month)


@router.get("/exceptions")
def control_tower_exceptions(
    billing_month: Optional[str] = Query(None, description="YYYY-MM"),
    code: Optional[str] = Query(None),
    queue: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(require_finance_control_tower_read()),
    db: Session = Depends(get_db),
):
    _ = user
    return tower.list_control_tower_exceptions(
        db, billing_month=billing_month, code=code, queue=queue, limit=limit
    )


@router.get("/billing-readiness")
def control_tower_billing_readiness(
    billing_month: Optional[str] = Query(None, description="YYYY-MM"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(require_finance_control_tower_read()),
    db: Session = Depends(get_db),
):
    _ = user
    return tower.list_billing_readiness(db, billing_month=billing_month, limit=limit)


@router.get("/payout-readiness")
def control_tower_payout_readiness(
    billing_month: Optional[str] = Query(None, description="YYYY-MM"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(require_finance_control_tower_read()),
    db: Session = Depends(get_db),
):
    _ = user
    return tower.list_payout_readiness(db, billing_month=billing_month, limit=limit)


@router.get("/billing-readiness-master-sheet")
def billing_readiness_master_sheet(
    billing_month: Optional[str] = Query(None, description="YYYY-MM"),
    service_type: Optional[str] = Query(None),
    client_type: Optional[str] = Query(None, description="Shadow, Homecare, Package, …"),
    client_status: Optional[str] = Query(None),
    exception_state: Optional[str] = Query(None, description="CLEAR, WARN, or BLOCK"),
    search: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(require_finance_control_tower_read()),
    db: Session = Depends(get_db),
):
    _ = user
    return master_sheet.list_billing_readiness_master_sheet(
        db,
        billing_month=billing_month,
        service_type=service_type,
        client_type=client_type,
        client_status=client_status,
        exception_state=exception_state,
        search=search,
        limit=limit,
    )
