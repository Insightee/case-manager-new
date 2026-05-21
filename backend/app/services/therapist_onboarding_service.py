from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.module_access import validate_module_assignments
from app.core.therapist_services import validate_service_ids
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import InviteToken, User
from app.services import auth_service, email_service, therapist_profile_service as profile_svc


def _invite_url(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/invite/{token}"


def _check_email_available(db: Session, email: str) -> None:
    email_l = email.lower().strip()
    if db.scalars(select(User).where(User.email == email_l)).first():
        raise ValueError("A user with this email already exists")
    now = datetime.now(timezone.utc)
    pending = db.scalars(
        select(InviteToken).where(
            InviteToken.email == email_l,
            InviteToken.used_at.is_(None),
            InviteToken.expires_at > now,
        )
    ).first()
    if pending:
        raise ValueError("A pending invite already exists for this email")


def _create_therapist_profile(
    db: Session,
    user: User,
    *,
    full_name: str,
    services_offered: list[str],
    short_bio: str | None,
    reviewed_by_user_id: int,
) -> TherapistProfile:
    existing = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user.id)).first()
    if existing:
        profile = existing
    else:
        profile = TherapistProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    profile.display_name = full_name.strip()
    if short_bio:
        profile.short_bio = short_bio.strip()
    if services_offered:
        profile.services_offered = validate_service_ids(services_offered)
    profile.status = TherapistProfileStatus.APPROVED
    profile.reviewed_by_user_id = reviewed_by_user_id
    profile.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return profile


def onboard_therapist_invite(
    db: Session,
    *,
    email: str,
    full_name: str,
    phone: str | None,
    module_assignments: list[str],
    services_offered: list[str],
    short_bio: str | None,
    created_by_user_id: int,
    send_email: bool,
) -> dict:
    _check_email_available(db, email)
    modules = validate_module_assignments(["THERAPIST"], module_assignments)
    services = validate_service_ids(services_offered) if services_offered else []

    token = secrets.token_urlsafe(32)
    invite = InviteToken(
        email=email.lower().strip(),
        role_name="THERAPIST",
        module_assignments=modules,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_user_id=created_by_user_id,
        invite_metadata={
            "full_name": full_name.strip(),
            "phone": (phone or "").strip() or None,
            "services_offered": services,
            "short_bio": short_bio,
        },
    )
    db.add(invite)
    db.flush()
    url = _invite_url(token)
    if send_email:
        email_service.therapist_staff_invite_email(
            to=invite.email,
            invite_url=url,
            full_name=full_name,
        )
    return {
        "email": invite.email,
        "invite_url": url,
        "invite_id": invite.id,
        "expires_at": invite.expires_at.isoformat(),
    }


def onboard_therapist_direct(
    db: Session,
    *,
    email: str,
    full_name: str,
    phone: str | None,
    password: str | None,
    module_assignments: list[str],
    services_offered: list[str],
    short_bio: str | None,
    created_by_user_id: int,
) -> dict:
    _check_email_available(db, email)
    modules = validate_module_assignments(["THERAPIST"], module_assignments)
    temp_password = password or secrets.token_urlsafe(10)
    user = auth_service.create_user(
        db,
        email=email.lower().strip(),
        password=temp_password,
        full_name=full_name.strip(),
        role_names=["THERAPIST"],
        module_assignments=modules,
    )
    if phone:
        user.phone = phone.strip()
    profile = _create_therapist_profile(
        db,
        user,
        full_name=full_name,
        services_offered=services_offered,
        short_bio=short_bio,
        reviewed_by_user_id=created_by_user_id,
    )
    return {
        "user_id": user.id,
        "email": user.email,
        "profile_id": profile.id,
        "temporary_password": temp_password if not password else None,
    }


def onboard_therapist(
    db: Session,
    *,
    email: str,
    full_name: str,
    phone: str | None = None,
    module_assignments: list[str] | None = None,
    services_offered: list[str] | None = None,
    mode: str = "invite",
    password: str | None = None,
    send_email: bool = True,
    short_bio: str | None = None,
    created_by_user_id: int,
) -> dict:
    mods = module_assignments or ["homecare", "shadow_support"]
    services = services_offered or []
    if mode == "direct":
        return onboard_therapist_direct(
            db,
            email=email,
            full_name=full_name,
            phone=phone,
            password=password,
            module_assignments=mods,
            services_offered=services,
            short_bio=short_bio,
            created_by_user_id=created_by_user_id,
        )
    return onboard_therapist_invite(
        db,
        email=email,
        full_name=full_name,
        phone=phone,
        module_assignments=mods,
        services_offered=services,
        short_bio=short_bio,
        created_by_user_id=created_by_user_id,
        send_email=send_email,
    )


def onboard_therapists_bulk(
    db: Session,
    rows: list[dict],
    *,
    mode: str,
    send_email: bool,
    created_by_user_id: int,
) -> list[dict]:
    results = []
    for row in rows:
        email = row.get("email", "").strip()
        try:
            data = onboard_therapist(
                db,
                email=email,
                full_name=row["full_name"],
                phone=row.get("phone"),
                module_assignments=row.get("module_assignments") or ["homecare", "shadow_support"],
                services_offered=row.get("services_offered") or [],
                mode=mode,
                send_email=send_email,
                created_by_user_id=created_by_user_id,
            )
            results.append(
                {
                    "email": email,
                    "success": True,
                    "user_id": data.get("user_id"),
                    "invite_url": data.get("invite_url"),
                    "temporary_password": data.get("temporary_password"),
                    "error": None,
                }
            )
        except Exception as e:
            results.append(
                {
                    "email": email,
                    "success": False,
                    "user_id": None,
                    "invite_url": None,
                    "temporary_password": None,
                    "error": str(e),
                }
            )
    return results


def apply_therapist_invite_metadata(db: Session, user: User, invite: InviteToken) -> None:
    meta = invite.invite_metadata or {}
    if meta.get("phone"):
        user.phone = meta["phone"]
    services = meta.get("services_offered") or []
    full_name = meta.get("full_name") or user.full_name
    _create_therapist_profile(
        db,
        user,
        full_name=full_name,
        services_offered=services,
        short_bio=meta.get("short_bio"),
        reviewed_by_user_id=invite.created_by_user_id or user.id,
    )
