from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.module_access import validate_module_assignments
from app.core.therapist_services import validate_service_ids
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import InviteToken, User
from app.services import auth_service, therapist_profile_service as profile_svc
from app.services.email.service import (
    enqueue_portal_invite_email,
    invite_email_delivery_status,
    therapist_staff_invite_email,
)


def _invite_url(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/invite/{token}"


def _ensure_email_free_for_new_user(db: Session, email: str) -> None:
    email_l = email.lower().strip()
    if db.scalars(select(User).where(User.email == email_l)).first():
        raise ValueError("A user with this email already exists")


def _assert_new_invite_allowed(db: Session, email: str, role_name: str) -> None:
    from app.services.invite_policy_service import assert_can_create_invite

    assert_can_create_invite(db, email, role_name)
    existing = db.scalars(select(User).where(User.email == email.lower().strip())).first()
    if existing:
        raise ValueError("User already exists. Use Invite to login instead of sending a new invite.")


def _create_therapist_profile(
    db: Session,
    user: User,
    *,
    full_name: str,
    services_offered: list[str],
    short_bio: str | None,
    reviewed_by_user_id: int,
    primary_case_manager_user_id: int | None = None,
    mentor_user_id: int | None = None,
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
    if primary_case_manager_user_id:
        profile.supervisor_user_id = primary_case_manager_user_id
    if mentor_user_id is not None:
        profile.mentor_user_id = mentor_user_id
    db.flush()
    return profile


def _apply_therapist_service_access(db: Session, user: User, services_offered: list[str]) -> None:
    from app.core.rbac_access import sync_user_access_fields
    from app.core.service_access import normalize_service_access_grants

    validated = validate_service_ids(services_offered, db) if services_offered else []
    svc_grants = normalize_service_access_grants(
        {sid: {"enabled": True, "access": "write"} for sid in validated}
    )
    sync_user_access_fields(
        user,
        role_names=["THERAPIST"],
        service_access_grants=svc_grants,
        module_assignments=validated,
        db=db,
    )


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
    background_tasks: BackgroundTasks | None = None,
    primary_case_manager_user_id: int,
    mentor_user_id: int | None = None,
) -> dict:
    _assert_new_invite_allowed(db, email, "THERAPIST")
    modules = validate_module_assignments(["THERAPIST"], module_assignments, db)
    services = validate_service_ids(services_offered, db) if services_offered else []

    token = secrets.token_urlsafe(32)
    invite = InviteToken(
        email=email.lower().strip(),
        role_name="THERAPIST",
        module_assignments=modules or services,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_user_id=created_by_user_id,
        invite_metadata={
            "full_name": full_name.strip(),
            "phone": (phone or "").strip() or None,
            "services_offered": services,
            "short_bio": short_bio,
            "primary_case_manager_user_id": primary_case_manager_user_id,
            "mentor_user_id": mentor_user_id,
        },
    )
    db.add(invite)
    db.flush()
    url = _invite_url(token)
    if send_email:
        if background_tasks is not None:
            enqueue_portal_invite_email(
                background_tasks,
                db,
                to=invite.email,
                invite_url=url,
                full_name=full_name,
                role_label="Therapist",
                recipient_role="therapist",
            )
        else:
            therapist_staff_invite_email(
                to=invite.email,
                invite_url=url,
                full_name=full_name,
            )
    return {
        "email": invite.email,
        "invite_url": url,
        "invite_id": invite.id,
        "expires_at": invite.expires_at.isoformat(),
        "email_delivery": invite_email_delivery_status(
            send_email=send_email, background_tasks=background_tasks
        ),
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
    primary_case_manager_user_id: int,
    mentor_user_id: int | None = None,
) -> dict:
    _ensure_email_free_for_new_user(db, email)
    validated_services = validate_service_ids(services_offered, db) if services_offered else []
    mods = module_assignments or validated_services
    validate_module_assignments(["THERAPIST"], mods, db)
    temp_password = password or secrets.token_urlsafe(10)
    user = auth_service.create_user(
        db,
        email=email.lower().strip(),
        password=temp_password,
        full_name=full_name.strip(),
        role_names=["THERAPIST"],
        module_assignments=mods,
    )
    if phone:
        user.phone = phone.strip()
    _apply_therapist_service_access(db, user, validated_services)
    profile = _create_therapist_profile(
        db,
        user,
        full_name=full_name,
        services_offered=validated_services,
        short_bio=short_bio,
        reviewed_by_user_id=created_by_user_id,
        primary_case_manager_user_id=primary_case_manager_user_id,
        mentor_user_id=mentor_user_id,
    )
    return {
        "user_id": user.id,
        "email": user.email,
        "profile_id": profile.id,
        "temporary_password": temp_password if not password else None,
        "email_delivery": "skipped_direct_mode",
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
    primary_case_manager_user_id: int,
    mentor_user_id: int | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> dict:
    services = services_offered or []
    mods = module_assignments or services
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
            primary_case_manager_user_id=primary_case_manager_user_id,
            mentor_user_id=mentor_user_id,
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
        background_tasks=background_tasks,
        primary_case_manager_user_id=primary_case_manager_user_id,
        mentor_user_id=mentor_user_id,
    )


def onboard_therapists_bulk(
    db: Session,
    rows: list[dict],
    *,
    mode: str,
    send_email: bool,
    created_by_user_id: int,
    primary_case_manager_user_id: int,
    mentor_user_id: int | None = None,
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
                module_assignments=row.get("module_assignments") or row.get("services_offered") or [],
                services_offered=row.get("services_offered") or [],
                mode=mode,
                send_email=send_email,
                created_by_user_id=created_by_user_id,
                primary_case_manager_user_id=primary_case_manager_user_id,
                mentor_user_id=mentor_user_id,
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
    _apply_therapist_service_access(db, user, services)
    _create_therapist_profile(
        db,
        user,
        full_name=full_name,
        services_offered=services,
        short_bio=meta.get("short_bio"),
        reviewed_by_user_id=invite.created_by_user_id or user.id,
        primary_case_manager_user_id=meta.get("primary_case_manager_user_id"),
        mentor_user_id=meta.get("mentor_user_id"),
    )
