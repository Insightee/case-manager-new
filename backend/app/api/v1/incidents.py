from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.incident_catalog import meta_payload
from app.core.pagination import paginate_query, paginated_response
from app.core.module_access import is_view_only_user, user_has_feature
from app.core.module_write import ensure_feature_write_access, guard_clinical_case
from app.core.permissions import RoleName, case_scope_check, require_mutation_permission, require_permission, user_has_permission
from app.models.incident import Incident, IncidentMessage, IncidentStatus, normalize_incident_status
from app.models.user import User
from app.models.case import Case
from app.services import case_service, incident_attachment_service as att_svc
from app.services import incident_flow_service as inc_flow
from app.services import incident_service as inc_svc
from app.services import incident_sla_service as sla_svc
from app.services import notification_service

router = APIRouter(prefix="/incidents", tags=["incidents"])


class IncidentCreate(BaseModel):
    case_id: Optional[int] = None
    primary_category: str
    subcategory: str
    what_happened: str = Field(..., min_length=3)
    priority: Optional[str] = None
    service_type: Optional[str] = None
    incident_at: Optional[datetime] = None
    location: Optional[str] = None
    immediate_action: Optional[str] = None
    child_safe: Optional[str] = None
    parent_informed: Optional[str] = None
    is_sensitive: bool = False
    # Legacy fallback
    title: Optional[str] = None
    description: Optional[str] = None


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    tagged_roles: Optional[list[str]] = None
    tagged_user_ids: Optional[list[int]] = None
    action_taken_note: Optional[str] = None


class IncidentMessageCreate(BaseModel):
    body: str


class IncidentFlowNote(BaseModel):
    note: str = Field(..., min_length=3)


class IncidentEscalateRequest(BaseModel):
    reason: Optional[str] = None


def _has_manage(user: User) -> bool:
    return user_has_permission(user, "incident.read_sensitive") and user_has_feature(user, "incidents")


def _is_therapist_reporter(user: User) -> bool:
    return RoleName.THERAPIST.value in user.role_names and not _has_manage(user)


def _service_type_from_case(case: Case) -> str:
    pm = (case.product_module or "").strip().lower()
    if pm:
        return pm
    return (case.service_type or "homecare").strip().lower()


def _guard_incident_write(user: User, incident: Incident, db: Session) -> None:
    if is_view_only_user(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="View-only access — changes are not allowed")
    if incident.case_id:
        case = case_service.get_case(db, incident.case_id)
        if case:
            guard_clinical_case(user, case, db, feature="incidents")
            return
    product = (incident.service_type or "homecare").strip().lower()
    ensure_feature_write_access(user, "incidents", product_module=product, db=db)


def _can_access(incident: Incident, user: User, db: Session) -> bool:
    if incident.reported_by_user_id == user.id:
        return True
    if _has_manage(user):
        if incident.case_id:
            case = case_service.get_case(db, incident.case_id)
            return case is None or case_scope_check(db, user, case)
        return True
    if incident.assigned_to_user_id == user.id:
        return True
    return False


@router.get("/meta")
def incidents_meta():
    return meta_payload()


@router.get("/attachments/{attachment_id}/download")
def download_incident_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    att = att_svc.get_attachment_or_404(db, attachment_id)
    incident = db.get(Incident, att.incident_id)
    if not incident or not att_svc.can_access_incident(db, user, incident):
        raise HTTPException(status_code=403, detail="Access denied")
    return att_svc.download_response(att)


@router.get("")
def list_incidents(
    product_module: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    primary_category: Optional[str] = None,
    assigned_to_me: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    has_manage = _has_manage(user)

    if has_manage:
        stmt = select(Incident).order_by(Incident.created_at.desc())
    elif assigned_to_me:
        stmt = (
            select(Incident)
            .where(
                or_(
                    Incident.assigned_to_user_id == user.id,
                    Incident.reported_by_user_id == user.id,
                )
            )
            .order_by(Incident.created_at.desc())
        )
    else:
        stmt = (
            select(Incident)
            .where(Incident.reported_by_user_id == user.id)
            .order_by(Incident.created_at.desc())
        )

    if status:
        stmt = stmt.where(Incident.status == normalize_incident_status(status))
    if priority:
        stmt = stmt.where(Incident.priority == priority.upper())
    if primary_category:
        stmt = stmt.where(Incident.primary_category == primary_category.upper())

    incidents, total = paginate_query(db, stmt, page=page, page_size=page_size)

    if has_manage:
        sla_svc.process_open_incidents(db, incidents)

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
        result.append(inc_svc.incident_to_list_dict(i, case))

    if has_manage:
        db.commit()

    return paginated_response(result, total, page, page_size)


@router.get("/{incident_id}")
def get_incident(
    incident_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = inc_svc.get_incident_detail(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not _can_access(incident, user, db):
        raise HTTPException(status_code=403, detail="Access denied")

    is_owner = incident.assigned_to_user_id == user.id and _has_manage(user)
    if is_owner:
        inc_svc.mark_in_review_on_owner_open(incident, user.id)
        db.commit()

    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    return inc_svc.incident_to_detail_dict(db, incident, case, user)


@router.post("/{incident_id}/close")
def close_incident_endpoint(
    incident_id: int,
    payload: IncidentFlowNote,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = inc_svc.get_incident_detail(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not _can_access(incident, user, db):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        inc_flow.close_incident(db, user, incident, note=payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="close", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    incident = inc_svc.get_incident_detail(db, incident_id)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    return inc_svc.incident_to_detail_dict(db, incident, case, user)


@router.post("/{incident_id}/escalate")
def escalate_incident_endpoint(
    incident_id: int,
    request: Request,
    payload: IncidentEscalateRequest = IncidentEscalateRequest(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = inc_svc.get_incident_detail(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not _can_access(incident, user, db):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        inc_flow.escalate_incident(db, user, incident, reason=payload.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="escalate", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    incident = inc_svc.get_incident_detail(db, incident_id)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    return inc_svc.incident_to_detail_dict(db, incident, case, user)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    what = payload.what_happened or payload.description or ""
    if not what.strip():
        raise HTTPException(status_code=400, detail="What happened is required")

    if _is_therapist_reporter(user) and not payload.case_id:
        raise HTTPException(status_code=400, detail="case_id is required for therapist incident reports")

    case = None
    if payload.case_id:
        case = case_service.get_case(db, payload.case_id)
        if not case or not case_scope_check(db, user, case):
            raise HTTPException(status_code=404, detail="Case not found")
        if _has_manage(user):
            guard_clinical_case(user, case, db, feature="incidents")

    service_type = payload.service_type
    if case:
        service_type = _service_type_from_case(case)
    elif _is_therapist_reporter(user):
        raise HTTPException(status_code=400, detail="case_id is required for therapist incident reports")

    try:
        incident = inc_svc.create_incident(
            db,
            reporter_user_id=user.id,
            reporter_role_names=user.role_names,
            case_id=payload.case_id,
            primary_category=payload.primary_category,
            subcategory=payload.subcategory,
            what_happened=what,
            priority=payload.priority,
            service_type=service_type,
            incident_at=payload.incident_at,
            location=payload.location,
            immediate_action=payload.immediate_action,
            child_safe=payload.child_safe,
            parent_informed=payload.parent_informed,
            is_sensitive=payload.is_sensitive,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    assignee_name = "the assigned owner"
    if incident.assigned_to_user_id:
        u = db.get(User, incident.assigned_to_user_id)
        if u:
            assignee_name = u.full_name
    notification_service.create_notification(
        db,
        user_id=user.id,
        title="Incident submitted",
        body=f"{incident.ticket_code} submitted — {assignee_name} will review.",
        entity_type="incident",
        entity_id=incident.id,
    )
    if incident.assigned_to_user_id:
        notification_service.create_notification(
            db,
            user_id=incident.assigned_to_user_id,
            title=f"New incident: {incident.ticket_code}",
            body=incident.title,
            entity_type="incident",
            entity_id=incident.id,
        )
    if incident.priority == "CRITICAL" and incident.assigned_to_user_id:
        from app.services.ticket_escalation_service import find_assignee_for_role
        from app.core.permissions import RoleName

        case = case_service.get_case(db, incident.case_id) if incident.case_id else None
        hr_id = find_assignee_for_role(db, RoleName.HR.value, case)
        if hr_id and hr_id != incident.assigned_to_user_id:
            notification_service.create_notification(
                db,
                user_id=hr_id,
                title=f"Critical incident: {incident.ticket_code}",
                body=incident.title,
                entity_type="incident",
                entity_id=incident.id,
            )

    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    db.refresh(incident)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    detail = inc_svc.incident_to_detail_dict(db, incident, case, user)
    detail["confirmation"] = f"Incident {incident.ticket_code} submitted — {assignee_name} will review."
    return detail


@router.post("/{incident_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_incident_attachments(
    incident_id: int,
    request: Request,
    note: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not att_svc.can_access_incident(db, user, incident):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        saved = await att_svc.save_attachments(db, incident, user, files, note=note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="attach", entity_type="incident", entity_id=incident_id, **meta)
    db.commit()
    return {"attachments": [att_svc.attachment_to_dict(a) for a in saved]}


@router.post("/{incident_id}/messages", status_code=status.HTTP_201_CREATED)
def add_incident_message(
    incident_id: int,
    payload: IncidentMessageCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    incident = inc_svc.get_incident_detail(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not _can_access(incident, user, db):
        raise HTTPException(status_code=403, detail="Access denied")

    is_reporter = incident.reported_by_user_id == user.id
    is_owner = incident.assigned_to_user_id == user.id and _has_manage(user)
    if is_owner:
        _guard_incident_write(user, incident, db)

    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message body is required")

    msg = IncidentMessage(
        incident_id=incident_id,
        author_user_id=user.id,
        body=body,
    )
    db.add(msg)

    if is_reporter and incident.status in (IncidentStatus.ACTION_TAKEN, IncidentStatus.CLOSED):
        incident.status = IncidentStatus.IN_REVIEW
    if is_owner:
        incident.last_owner_activity_at = datetime.now(timezone.utc)
        if incident.status == IncidentStatus.REPORTED:
            incident.status = IncidentStatus.IN_REVIEW

    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="message", entity_type="incident", entity_id=incident_id, **meta)
    db.commit()
    incident = inc_svc.get_incident_detail(db, incident_id)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    return inc_svc.incident_to_detail_dict(db, incident, case, user)


@router.patch("/{incident_id}")
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    request: Request,
    user: User = Depends(require_mutation_permission("incident.read_sensitive")),
    db: Session = Depends(get_db),
):
    if not user_has_feature(user, "incidents"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incidents module access required")
    incident = inc_svc.get_incident_detail(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.case_id:
        case = case_service.get_case(db, incident.case_id)
        if case and not case_scope_check(db, user, case):
            raise HTTPException(status_code=403, detail="Case access denied")
    _guard_incident_write(user, incident, db)

    is_owner = incident.assigned_to_user_id == user.id or user_has_permission(user, "admin.override")
    from app.services import incident_notify_service as inc_notify

    before_tagged = inc_notify.collect_tagged_user_ids(db, incident)
    try:
        inc_svc.update_incident(
            db,
            incident,
            actor_user_id=user.id,
            is_owner=is_owner,
            status=payload.status,
            priority=payload.priority,
            assigned_to_user_id=payload.assigned_to_user_id,
            tagged_roles=payload.tagged_roles,
            tagged_user_ids=payload.tagged_user_ids,
            action_taken_note=payload.action_taken_note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.tagged_roles is not None or payload.tagged_user_ids is not None:
        after_tagged = inc_notify.collect_tagged_user_ids(db, incident)
        new_ids = after_tagged - before_tagged
        inc_notify.notify_incident_tagged(db, incident, user.id, notify_user_ids=new_ids)

    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="incident", entity_id=incident.id, **meta)
    db.commit()
    incident = inc_svc.get_incident_detail(db, incident_id)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    return inc_svc.incident_to_detail_dict(db, incident, case, user)
