from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.case_service import CaseService, CaseServiceStatus


def normalize_service_key(service_key: str) -> str:
    return (service_key or "").strip().lower().replace(" ", "_")


def list_case_services(db: Session, case_id: int) -> list[CaseService]:
    return list(
        db.scalars(
            select(CaseService).where(CaseService.case_id == case_id).order_by(CaseService.id.asc())
        ).all()
    )


def get_case_service(db: Session, case_service_id: int) -> CaseService | None:
    return db.get(CaseService, case_service_id)


def create_case_service(
    db: Session,
    *,
    case_id: int,
    service_key: str,
    product_module: str | None = None,
    start_date: date | None = None,
    notes: str | None = None,
    status: CaseServiceStatus = CaseServiceStatus.ACTIVE,
) -> CaseService:
    key = normalize_service_key(service_key)
    if not key:
        raise ValueError("service_key is required")
    existing = db.scalars(
        select(CaseService).where(
            CaseService.case_id == case_id,
            CaseService.service_key == key,
            CaseService.status == status,
        )
    ).first()
    if existing:
        raise ValueError("Service already exists for this case")
    row = CaseService(
        case_id=case_id,
        service_key=key,
        product_module=(product_module or "").strip().lower() or None,
        status=status,
        start_date=start_date,
        notes=notes,
    )
    db.add(row)
    db.flush()
    return row


def update_case_service(
    db: Session,
    *,
    case_service_id: int,
    status: CaseServiceStatus | None = None,
    end_date: date | None = None,
    notes: str | None = None,
) -> CaseService:
    row = db.get(CaseService, case_service_id)
    if not row:
        raise ValueError("Service line not found")
    if status is not None:
        row.status = status
    if end_date is not None:
        row.end_date = end_date
    if notes is not None:
        row.notes = notes
    db.flush()
    return row


def ensure_default_case_service(db: Session, case: Case) -> CaseService:
    existing = db.scalars(
        select(CaseService).where(
            CaseService.case_id == case.id,
            CaseService.status == CaseServiceStatus.ACTIVE,
        )
    ).first()
    if existing:
        return existing
    return create_case_service(
        db,
        case_id=case.id,
        service_key=case.service_type or "general",
        product_module=case.product_module,
        start_date=case.created_at.date() if case.created_at else None,
        notes="Auto-created default case service",
    )
