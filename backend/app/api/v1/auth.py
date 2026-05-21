from __future__ import annotations

from typing import Optional

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.security import decode_refresh_token, is_refresh_token_valid, revoke_refresh_token
from app.models.role import Role
from app.models.user import InviteToken, User
from app.core.module_access import get_user_features, modules_for_api
from app.models.user import EmploymentStatus
from app.schemas.auth import AcceptInviteRequest, LoginRequest, MeUpdate, ModuleSummary, RefreshRequest, TokenResponse, UserMeResponse
from app.services import address_service, auth_service, avatar_service
from app.services.address_service import user_home_address_read

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access, refresh = auth_service.issue_tokens(user)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="login", entity_type="user", entity_id=user.id, **meta)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = decode_refresh_token(payload.refresh_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if data.get("type") != "refresh" or not is_refresh_token_valid(data.get("jti", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.role import Role

    user = db.scalars(
        select(User)
        .where(User.id == int(data["sub"]), User.is_active.is_(True))
        .options(selectinload(User.roles).selectinload(Role.permissions))
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    access, new_refresh = auth_service.issue_tokens(user)
    revoke_refresh_token(data["jti"])
    db.commit()
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.post("/accept-invite", response_model=TokenResponse)
def accept_invite(payload: AcceptInviteRequest, request: Request, db: Session = Depends(get_db)):
    invite = db.scalars(select(InviteToken).where(InviteToken.token == payload.token)).first()
    if not invite or invite.used_at:
        raise HTTPException(status_code=400, detail="Invalid or used invite")
    if invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite expired")
    existing = db.scalars(select(User).where(User.email == invite.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    user = auth_service.create_user(
        db,
        email=invite.email,
        password=payload.password,
        full_name=payload.full_name,
        role_names=[invite.role_name],
        module_assignments=invite.module_assignments or [],
    )
    if invite.role_name == "PARENT":
        from app.models.child import Child
        from app.models.parent import ParentGuardian
        from app.services.parent_service import dedupe_parent_child_links

        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == user.id)).first()
        if not pg:
            pg = ParentGuardian(user_id=user.id)
            db.add(pg)
            db.flush()
        if invite.linked_child_id:
            child = db.get(Child, invite.linked_child_id)
            if child and child not in pg.children:
                pg.children.append(child)
        dedupe_parent_child_links(db, pg.id)
    elif invite.role_name == "THERAPIST":
        from app.services.therapist_onboarding_service import apply_therapist_invite_metadata

        apply_therapist_invite_metadata(db, user, invite)
    invite.used_at = datetime.now(timezone.utc)
    if invite.invite_metadata and invite.invite_metadata.get("pending_slot_id"):
        from app.services import appointment_notification_service as appt_ns

        appt_ns.notify_parent_invite_accepted_admin(
            db, user_email=user.email, full_name=user.full_name
        )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="accept_invite", entity_type="user", entity_id=user.id, **meta)
    db.commit()
    user = db.scalars(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    ).first()
    access, refresh = auth_service.issue_tokens(user)
    return TokenResponse(access_token=access, refresh_token=refresh)


def _avatar_url(user: User) -> Optional[str]:
    if user.avatar_path:
        return avatar_service.avatar_public_path(user.id)
    return None


def _user_me_response(user: User) -> UserMeResponse:
    module_summaries = [ModuleSummary(**m) for m in modules_for_api(user)]
    return UserMeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        avatar_url=_avatar_url(user),
        roles=user.role_names,
        permissions=sorted(user.permission_names),
        region=user.region,
        location=user.location,
        home_address=user_home_address_read(user),
        employment_status=(user.employment_status.value if user.employment_status else "ACTIVE"),
        module_assignments=user.module_assignments or [],
        features=get_user_features(user),
        modules=module_summaries,
    )


@router.get("/me", response_model=UserMeResponse)
def me(user: User = Depends(get_current_user)):
    return _user_me_response(user)


@router.patch("/me", response_model=UserMeResponse)
def update_me(
    payload: MeUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone is not None:
        phone = payload.phone.strip() if payload.phone else None
        user.phone = phone or None
    if payload.location is not None:
        user.location = payload.location
    home_data = address_service.home_address_from_me_update(payload.model_dump(exclude_unset=True))
    if home_data:
        address_service.validate_home_address_payload(home_data)
        address_service.apply_home_address_to_user(user, home_data)
    if payload.employment_status is not None:
        allowed = {EmploymentStatus.ACTIVE.value, EmploymentStatus.SUSPENDED.value}
        if payload.employment_status not in allowed:
            raise HTTPException(status_code=400, detail="Therapists may only set status to ACTIVE or SUSPENDED")
        user.employment_status = EmploymentStatus(payload.employment_status)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update_profile", entity_type="user", entity_id=user.id, **meta)
    db.commit()
    db.refresh(user)
    return _user_me_response(user)


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    request: Request = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    try:
        ext = avatar_service.validate_avatar_upload(file.content_type, len(content))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    path = avatar_service.save_avatar(user.id, content, ext)
    user.avatar_path = path
    meta = get_request_meta(request) if request else {}
    log_audit(db, actor_user_id=user.id, action="upload_avatar", entity_type="user", entity_id=user.id, **meta)
    db.commit()
    return {"avatar_url": _avatar_url(user)}


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
def delete_avatar(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    avatar_service.delete_avatar_files(user.id)
    user.avatar_path = None
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="delete_avatar", entity_type="user", entity_id=user.id, **meta)
    db.commit()
    return None
