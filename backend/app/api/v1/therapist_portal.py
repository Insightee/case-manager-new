from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import require_permission, user_has_permission
from app.models.user import User
from app.schemas.session import TherapistClientIntakeCreate, TherapistClientIntakeResponse
from app.schemas.session_log_portal import (
    SessionLogCreate,
    SessionLogRead,
    TherapistMyCasesResponse,
)
from app.schemas.therapist_home import (
    TherapistHomeResponse,
    TherapistReportsPipelineResponse,
    TherapistSessionsWorkspaceResponse,
)
from app.services import session_log_service, therapist_home_service, therapist_intake_service

router = APIRouter(prefix="/therapist", tags=["therapist-portal"])


def _require_therapist(user: User) -> None:
    if not user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        raise HTTPException(status_code=403, detail="Therapist access required")


@router.get("/my-cases", response_model=TherapistMyCasesResponse)
def therapist_my_cases(
    user: User = Depends(require_permission("case.read.assigned")),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    data = session_log_service.list_therapist_my_cases(db, user)
    return TherapistMyCasesResponse(**data)


@router.post("/session-logs", response_model=SessionLogRead, status_code=status.HTTP_201_CREATED)
def therapist_create_session_log(
    payload: SessionLogCreate,
    request: Request,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    try:
        log = session_log_service.create_therapist_session_log(db, user, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type="daily_log",
        entity_id=log.id,
        new_value=payload.model_dump(),
        **meta,
    )
    db.commit()
    return SessionLogRead(**session_log_service.session_log_read(db, log))


@router.get("/home", response_model=TherapistHomeResponse)
def therapist_home(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    return therapist_home_service.build_therapist_home(db, user)


@router.get("/sessions/workspace", response_model=TherapistSessionsWorkspaceResponse)
def therapist_sessions_workspace(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    return therapist_home_service.build_sessions_workspace(db, user)


@router.get("/reports/pipeline", response_model=TherapistReportsPipelineResponse)
def therapist_reports_pipeline(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    return therapist_home_service.build_reports_pipeline(db, user)


@router.post("/client-intake", response_model=TherapistClientIntakeResponse, status_code=201)
def therapist_client_intake(
    payload: TherapistClientIntakeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.core.permissions import user_has_permission

    if not user_has_permission(user, "session.create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    _require_therapist(user)
    try:
        result = therapist_intake_service.create_client_intake(
            db,
            therapist_user_id=user.id,
            client_name=payload.client_name,
            client_email=str(payload.client_email),
            child_name=payload.child_name,
            client_phone=payload.client_phone,
            product_module=payload.product_module,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    case = result["case"]
    db.commit()
    from app.services import case_service

    case = case_service.get_case(db, case.id)
    child_name = case.child.full_name if case and case.child else payload.child_name
    return TherapistClientIntakeResponse(
        case_id=case.id,
        case_code=case.case_code,
        child_name=child_name,
        parent_email=result["parent_email"],
        invite_sent=result["invite_sent"],
        invite_url=result.get("invite_url"),
    )


# Therapist Chat Endpoints

from app.schemas.chat import MessageCreate, MessageRead, CaseChatTab
from typing import List
from fastapi import UploadFile, File

@router.get("/chats", response_model=List[CaseChatTab])
def therapist_list_chats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus
    from app.models.case import Case
    from sqlalchemy import select, func
    from app.models.parent_therapist_message import ParentTherapistMessage
    from app.services.parent_service import primary_parent_user_id_for_child

    # Find active case assignments for this therapist
    active_assignments = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.therapist_user_id == user.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE
        )
    ).all()

    tabs = []
    for assign in active_assignments:
        case = db.get(Case, assign.case_id)
        if not case:
            continue
        child_name = case.child.full_name if case.child else "Unknown Kid"
        
        parent_name = None
        parent_user_id = primary_parent_user_id_for_child(db, case.child_id) if case.child_id else None
        if parent_user_id:
            parent_user = db.get(User, parent_user_id)
            if parent_user:
                parent_name = parent_user.full_name

        unread_count = db.scalar(
            select(func.count(ParentTherapistMessage.id))
            .where(
                ParentTherapistMessage.case_id == case.id,
                ParentTherapistMessage.recipient_id == user.id,
                ParentTherapistMessage.is_read == False
            )
        ) or 0

        tabs.append({
            "case_id": case.id,
            "child_name": child_name,
            "case_code": case.case_code,
            "therapist_name": user.full_name,
            "parent_name": parent_name,
            "unread_count": unread_count
        })

    return tabs


@router.get("/chats/{case_id}/messages", response_model=dict)
def therapist_get_chat_messages(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus
    from app.models.case import Case
    from sqlalchemy import select, update
    from app.models.parent_therapist_message import ParentTherapistMessage
    from app.services.parent_service import primary_parent_user_id_for_child

    # Verify authorization
    is_active = db.scalar(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id == user.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE
        )
    ) is not None
    if not is_active:
        raise HTTPException(status_code=403, detail="Not authorized to access this case chat")

    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    parent_info = None
    parent_user_id = primary_parent_user_id_for_child(db, case.child_id) if case.child_id else None
    if parent_user_id:
        parent_user = db.get(User, parent_user_id)
        if parent_user:
            parent_info = {
                "id": parent_user.id,
                "full_name": parent_user.full_name
            }

    # Mark incoming messages as read
    db.execute(
        update(ParentTherapistMessage)
        .where(
            ParentTherapistMessage.case_id == case_id,
            ParentTherapistMessage.recipient_id == user.id,
            ParentTherapistMessage.is_read == False
        )
        .values(is_read=True)
    )
    db.commit()

    messages_rows = []
    if parent_user_id:
        messages_rows = db.scalars(
            select(ParentTherapistMessage)
            .where(
                ParentTherapistMessage.case_id == case_id,
                (
                    (ParentTherapistMessage.sender_id == user.id) &
                    (ParentTherapistMessage.recipient_id == parent_user_id)
                ) | (
                    (ParentTherapistMessage.sender_id == parent_user_id) &
                    (ParentTherapistMessage.recipient_id == user.id)
                )
            )
            .order_by(ParentTherapistMessage.created_at.asc())
        ).all()

    return {
        "messages": [MessageRead.model_validate(m) for m in messages_rows],
        "parent_info": parent_info
    }


@router.post("/chats/{case_id}/messages", response_model=MessageRead)
def therapist_send_chat_message(
    case_id: int,
    payload: MessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus
    from app.models.case import Case
    from sqlalchemy import select
    from app.models.parent_therapist_message import ParentTherapistMessage
    from app.services.parent_service import primary_parent_user_id_for_child

    is_active = db.scalar(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id == user.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE
        )
    ) is not None
    if not is_active:
        raise HTTPException(status_code=403, detail="Not authorized to message on this case")

    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    parent_user_id = primary_parent_user_id_for_child(db, case.child_id) if case.child_id else None
    if not parent_user_id:
        raise HTTPException(status_code=400, detail="No parent associated with this case child")

    new_msg = ParentTherapistMessage(
        case_id=case_id,
        sender_id=user.id,
        recipient_id=parent_user_id,
        body=payload.body
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    return new_msg


@router.post("/chats/{case_id}/upload", response_model=MessageRead)
async def therapist_upload_chat_attachment(
    case_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus
    from app.models.case import Case
    from sqlalchemy import select
    from app.models.parent_therapist_message import ParentTherapistMessage
    from app.services.parent_service import primary_parent_user_id_for_child

    is_active = db.scalar(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id == user.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE
        )
    ) is not None
    if not is_active:
        raise HTTPException(status_code=403, detail="Not authorized to message on this case")

    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    parent_user_id = primary_parent_user_id_for_child(db, case.child_id) if case.child_id else None
    if not parent_user_id:
        raise HTTPException(status_code=400, detail="No parent associated with this case child")

    # Enforce 10MB limit
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
    if not content:
        raise HTTPException(status_code=400, detail="Empty file not allowed")

    from app.storage.object_io import put_stored_bytes
    mime = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
    storage_key, _provider = put_stored_bytes(
        "chats",
        f"case_{case_id}",
        "attachments",
        filename=file.filename or "file",
        data=content,
        content_type=mime,
    )

    new_msg = ParentTherapistMessage(
        case_id=case_id,
        sender_id=user.id,
        recipient_id=parent_user_id,
        body=f"Sent a photo: {file.filename}",
        attachment_path=storage_key,
        attachment_name=file.filename or "attachment"
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    return new_msg
