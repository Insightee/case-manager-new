"""Read-only API for materialized Clinical Evidence Event Contract objects."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.clinical_evidence_contract import CONTRACT_STATUS, CONTRACT_VERSION
from app.models.user import User
from app.services import case_service, log_service
from app.services import clinical_evidence_event_service as cee_svc
from app.core.permissions import case_scope_check

router = APIRouter(tags=["clinical-evidence-events"])


def _log_case_scope(db: Session, user: User, log) -> None:
    if not log.session:
        raise HTTPException(status_code=404, detail="Log not found")
    case = case_service.get_case(db, log.session.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")


def _case_for_user(db: Session, user: User, case_id: int):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("/daily-logs/{log_id}/clinical-evidence-events")
def get_log_clinical_evidence_events(
    log_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)
    events = cee_svc.materialize_from_log(db, log_id)
    return {
        "contract_version": CONTRACT_VERSION,
        "contract_status": CONTRACT_STATUS,
        "daily_log_id": log_id,
        "events": events,
        "rollup": cee_svc.rollup_events(events),
    }


@router.get("/cases/{case_id}/clinical-evidence-events")
def get_case_clinical_evidence_events(
    case_id: int,
    month: str = Query(..., description="Report month YYYY-MM"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    events = cee_svc.materialize_for_case_month(db, case_id, month)
    return {
        "contract_version": CONTRACT_VERSION,
        "contract_status": CONTRACT_STATUS,
        "case_id": case_id,
        "month": month,
        "events": events,
        "rollup": cee_svc.rollup_events(events),
    }
