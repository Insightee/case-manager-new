from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.pagination import paginate_query, paginated_response
from app.core.module_access import user_has_feature
from app.core.permissions import case_scope_check, require_permission
from app.models.incident import Incident, IncidentStatus
from app.models.user import User
from app.services import case_service

router = APIRouter(prefix="/incidents", tags=["incidents"])


class IncidentCreate(BaseModel):
    case_id: Optional[int] = None
    title: str
    description: str
    is_sensitive: bool = False


class IncidentUpdate(BaseModel):
    status: Optional[IncidentStatus] = None
    assigned_to_user_id: Optional[int] = None


@router.get("")
def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_permission("incident.read_sensitive")),
    db: Session = Depends(get_db),
):
    if not user_has_feature(user, "incidents"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incidents module access required")

    stmt = select(Incident).order_by(Incident.created_at.desc())
    incidents, total = paginate_query(db, stmt, page=page, page_size=page_size)
    case_ids = {i.case_id for i in incidents if i.case_id}
    cases_by_id = {}
    if case_ids:
        from app.models.case import Case

        cases = db.scalars(select(Case).where(Case.id.in_(case_ids))).all()
        cases_by_id = {c.id: c for c in cases}
    result = []
    for i in incidents:
        case = cases_by_id.get(i.case_id) if i.case_id else None
        if case and not case_scope_check(db, user, case):
            continue
        result.append(
            {
                "id": i.id,
                "case_id": i.case_id,
                "title": i.title,
                "status": i.status.value,
                "is_sensitive": i.is_sensitive,
                "product_module": case.product_module if case else None,
            }
        )
    return paginated_response(result, total, page, page_size)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = Incident(
        case_id=payload.case_id,
        reported_by_user_id=user.id,
        title=payload.title,
        description=payload.description,
        is_sensitive=payload.is_sensitive,
    )
    db.add(incident)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    return {"id": incident.id, "status": incident.status.value}


@router.patch("/{incident_id}")
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    request: Request,
    user: User = Depends(require_permission("incident.read_sensitive")),
    db: Session = Depends(get_db),
):
    if not user_has_feature(user, "incidents"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incidents module access required")
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.case_id:
        case = case_service.get_case(db, incident.case_id)
        if case and not case_scope_check(db, user, case):
            raise HTTPException(status_code=403, detail="Case access denied")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        incident.status = data["status"]
    if "assigned_to_user_id" in data:
        incident.assigned_to_user_id = data["assigned_to_user_id"]
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    return {
        "id": incident.id,
        "status": incident.status.value,
        "assigned_to_user_id": incident.assigned_to_user_id,
    }
