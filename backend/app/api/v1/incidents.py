from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.pagination import paginate_query, paginated_response
from app.core.module_access import user_has_feature
from app.core.permissions import case_scope_check, require_permission, user_has_permission
from app.models.incident import Incident, IncidentMessage, IncidentStatus
from app.models.user import User
from app.models.case import Case
from app.services import case_service
from app.services import ticket_escalation_service as ticket_esc
from app.core.permissions import RoleName

router = APIRouter(prefix="/incidents", tags=["incidents"])


# ── Pydantic schemas ────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    case_id: Optional[int] = None
    title: str
    description: str
    is_sensitive: bool = False


class IncidentUpdate(BaseModel):
    status: Optional[IncidentStatus] = None
    assigned_to_user_id: Optional[int] = None


class IncidentMessageCreate(BaseModel):
    body: str


# ── Helpers ─────────────────────────────────────────────────────────────────

def _has_manage(user: User) -> bool:
    """True for super-admin / supervisor with incidents module."""
    return user_has_permission(user, "incident.read_sensitive") and user_has_feature(user, "incidents")


def _serialize_detail(incident: Incident, db: Session, viewer_user_id: int) -> dict:
    reporter = incident.reporter
    assignee = incident.assignee
    case = None
    if incident.case_id:
        case = db.scalars(
            select(Case).where(Case.id == incident.case_id).options(selectinload(Case.child))
        ).first()
    return {
        "id": incident.id,
        "case_id": incident.case_id,
        "case_code": case.case_code if case else None,
        "child_name": case_service.case_child_display_name(case),
        "title": incident.title,
        "description": incident.description,
        "is_sensitive": incident.is_sensitive,
        "status": incident.status.value,
        "product_module": case.product_module if case else None,
        "reporter_name": reporter.full_name if reporter else None,
        "assigned_to_user_id": incident.assigned_to_user_id,
        "assigned_to_name": assignee.full_name if assignee else None,
        "created_at": incident.created_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "body": m.body,
                "author_name": m.author.full_name if m.author else "Unknown",
                "is_reporter": m.author_user_id == incident.reported_by_user_id,
                "created_at": m.created_at.isoformat(),
            }
            for m in incident.messages
        ],
    }


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def list_incidents(
    product_module: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Supervisors/admins see all incidents (module-gated).
    Other authenticated users (therapists, etc.) see only incidents they reported.
    """
    has_manage = _has_manage(user)

    if has_manage:
        stmt = select(Incident).order_by(Incident.created_at.desc())
    else:
        stmt = (
            select(Incident)
            .where(Incident.reported_by_user_id == user.id)
            .order_by(Incident.created_at.desc())
        )

    incidents, total = paginate_query(db, stmt, page=page, page_size=page_size)

    case_ids = {i.case_id for i in incidents if i.case_id}
    cases_by_id = {}
    if case_ids:
        cases = db.scalars(
            select(Case).where(Case.id.in_(case_ids)).options(selectinload(Case.child))
        ).all()
        cases_by_id = {c.id: c for c in cases}

    result = []
    for i in incidents:
        case = cases_by_id.get(i.case_id) if i.case_id else None
        if has_manage and case and not case_scope_check(db, user, case):
            continue
        if product_module and (not case or case.product_module != product_module):
            continue
        result.append({
            "id": i.id,
            "case_id": i.case_id,
            "case_code": case.case_code if case else None,
            "child_name": case_service.case_child_display_name(case),
            "title": i.title,
            "status": i.status.value,
            "is_sensitive": i.is_sensitive,
            "product_module": case.product_module if case else None,
            "reporter_name": i.reporter.full_name if i.reporter else None,
            "created_at": i.created_at.isoformat(),
        })

    return paginated_response(result, total, page, page_size)


@router.get("/{incident_id}")
def get_incident(
    incident_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    has_manage = _has_manage(user)
    is_reporter = incident.reported_by_user_id == user.id

    if not has_manage and not is_reporter:
        raise HTTPException(status_code=403, detail="Access denied")

    return _serialize_detail(incident, db, user.id)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, payload.case_id) if payload.case_id else None
    assignee_id = None
    if case:
        if case.case_manager_user_id:
            assignee_id = case.case_manager_user_id
        else:
            assignee_id = ticket_esc.find_assignee_for_role(db, RoleName.SUPERVISOR.value, case)
    incident = Incident(
        case_id=payload.case_id,
        reported_by_user_id=user.id,
        title=payload.title,
        description=payload.description,
        is_sensitive=payload.is_sensitive,
        assigned_to_user_id=assignee_id,
    )
    db.add(incident)
    db.flush()

    # Add the description as the first message so the thread always starts with context
    first_msg = IncidentMessage(
        incident_id=incident.id,
        author_user_id=user.id,
        body=payload.description,
    )
    db.add(first_msg)

    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    return {"id": incident.id, "status": incident.status.value}


@router.post("/{incident_id}/messages", status_code=status.HTTP_201_CREATED)
def add_incident_message(
    incident_id: int,
    payload: IncidentMessageCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    has_manage = _has_manage(user)
    is_reporter = incident.reported_by_user_id == user.id

    if not has_manage and not is_reporter:
        raise HTTPException(status_code=403, detail="Access denied")

    msg = IncidentMessage(
        incident_id=incident_id,
        author_user_id=user.id,
        body=payload.body.strip(),
    )
    db.add(msg)

    # Reopen if resolved and reporter replies
    if is_reporter and incident.status == IncidentStatus.RESOLVED:
        incident.status = IncidentStatus.INVESTIGATING

    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="message", entity_type="incident", entity_id=incident_id, **meta)
    db.commit()
    db.refresh(incident)
    return _serialize_detail(incident, db, user.id)


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
    db.refresh(incident)
    return _serialize_detail(incident, db, user.id)
