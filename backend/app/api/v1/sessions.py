from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.pagination import paginate_query, paginated_response
from app.core.permissions import case_scope_check, require_permission, user_has_permission
from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.schemas.session import ManualSessionCreate, SessionCreate, SessionRead, SessionUpdate
from app.services import case_service, session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _session_read(s: TherapySession, case: Optional[Case] = None) -> SessionRead:
    child_name = None
    if case and case.child:
        child_name = case.child.full_name
    elif getattr(s, "case", None) and s.case.child:
        child_name = s.case.child.full_name
        case = s.case
    return SessionRead(
        id=s.id,
        case_id=s.case_id,
        case_code=case.case_code if case else None,
        child_name=child_name,
        therapist_user_id=s.therapist_user_id,
        scheduled_date=s.scheduled_date,
        start_time=s.start_time,
        end_time=s.end_time,
        actual_start_at=s.actual_start_at,
        actual_end_at=s.actual_end_at,
        auto_ended=bool(s.auto_ended),
        mode=s.mode,
        status=s.status,
        has_daily_log=s.daily_log is not None,
    )


def _therapist_only_update(user: User, session: TherapySession) -> None:
    if user_has_permission(user, "case.read.all"):
        return
    if session.therapist_user_id != user.id:
        raise HTTPException(status_code=403, detail="Can only update your own sessions")


@router.get("")
def list_sessions(
    case_id: Optional[int] = None,
    therapist_user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_permission("session.read")),
    db: Session = Depends(get_db),
):
    stmt = select(TherapySession).options(
        selectinload(TherapySession.daily_log),
        selectinload(TherapySession.case).selectinload(Case.child),
    )
    if case_id:
        stmt = stmt.where(TherapySession.case_id == case_id)
    if therapist_user_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    elif user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        stmt = stmt.where(TherapySession.therapist_user_id == user.id)
    stmt = stmt.order_by(TherapySession.scheduled_date.desc())
    sessions, total = paginate_query(db, stmt, page=page, page_size=page_size)
    result = []
    for s in sessions:
        case = s.case or db.get(Case, s.case_id)
        if case and case_scope_check(db, user, case):
            if s.status == SessionStatus.IN_PROGRESS:
                s = session_service.auto_end_if_stale(db, s)
            result.append(_session_read(s, case))
    db.commit()
    return paginated_response([r.model_dump() for r in result], total, page, page_size)


@router.get("/upcoming", response_model=list[SessionRead])
def upcoming_sessions(
    days: int = Query(7, ge=1, le=30),
    user: User = Depends(require_permission("session.read")),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        raise HTTPException(status_code=403, detail="Therapist access required")
    therapist_id = user.id
    sessions = session_service.list_upcoming_sessions(db, therapist_id, days=days)
    return [_session_read(s, s.case) for s in sessions if s.case and case_scope_check(db, user, s.case)]


@router.get("/active", response_model=Optional[SessionRead])
def active_session(
    user: User = Depends(require_permission("session.read")),
    db: Session = Depends(get_db),
):
    session = session_service.get_active_session(db, user.id)
    db.commit()
    if not session:
        return None
    return _session_read(session, session.case)


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    request: Request,
    user: User = Depends(require_permission("session.create")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, payload.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    data = payload.model_dump()
    if user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        data["therapist_user_id"] = user.id
    session = TherapySession(**data)
    db.add(session)
    db.flush()
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="session", entity_id=session.id, new_value=payload.model_dump(), **meta)
    db.commit()
    db.refresh(session)
    return _session_read(session, case)


@router.post("/manual", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_manual_session(
    payload: ManualSessionCreate,
    request: Request,
    user: User = Depends(require_permission("session.create")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, payload.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        session = session_service.create_manual_session(
            db,
            case_id=payload.case_id,
            therapist_user_id=user.id,
            scheduled_date=payload.scheduled_date,
            actual_start_at=payload.actual_start_at,
            actual_end_at=payload.actual_end_at,
            mode=payload.mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create_manual", entity_type="session", entity_id=session.id, **meta)
    db.commit()
    db.refresh(session)
    return _session_read(session, case)


@router.patch("/{session_id}", response_model=SessionRead)
def update_session(
    session_id: int,
    payload: SessionUpdate,
    request: Request,
    user: User = Depends(require_permission("session.update")),
    db: Session = Depends(get_db),
):
    session = db.get(TherapySession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    case = case_service.get_case(db, session.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Access denied")
    _therapist_only_update(user, session)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(session, k, v)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="session", entity_id=session.id, **meta)
    db.commit()
    return _session_read(session, case)


@router.post("/{session_id}/start", response_model=SessionRead)
def start_session(
    session_id: int,
    request: Request,
    user: User = Depends(require_permission("session.update")),
    db: Session = Depends(get_db),
):
    session = db.scalars(
        select(TherapySession)
        .where(TherapySession.id == session_id)
        .options(selectinload(TherapySession.case).selectinload(Case.child), selectinload(TherapySession.daily_log))
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    case = session.case
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        session = session_service.start_session(db, session, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="start", entity_type="session", entity_id=session.id, **meta)
    db.commit()
    return _session_read(session, case)


@router.post("/{session_id}/end", response_model=SessionRead)
def end_session(
    session_id: int,
    request: Request,
    user: User = Depends(require_permission("session.update")),
    db: Session = Depends(get_db),
):
    session = db.scalars(
        select(TherapySession)
        .where(TherapySession.id == session_id)
        .options(selectinload(TherapySession.case).selectinload(Case.child), selectinload(TherapySession.daily_log))
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    case = session.case
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Access denied")
    if session.therapist_user_id != user.id:
        raise HTTPException(status_code=403, detail="Can only end your own sessions")
    try:
        session = session_service.end_session(db, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="end", entity_type="session", entity_id=session.id, **meta)
    db.commit()
    return _session_read(session, case)
