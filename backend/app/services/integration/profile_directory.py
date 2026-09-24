"""Therapist listing reads and creates for website integration keys.

Responses keep HR fields (leave, TDS, snapshots, admin notes) off the wire.
Creating a profile never completes a report or edits clinical notes.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.config import settings
from app.core.pagination import normalize_pagination, paginate_query, paginated_response
from app.core.permissions import RoleName
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import User
from app.services import therapist_profile_service as profile_svc
from app.services.integration.access import IntegrationPrincipal, require_scope
from app.services.integration.errors import NotFoundError, ValidationError
from app.services.integration.rate_limit import check_rate_limit

_LISTING_FIELDS = (
    "display_name",
    "short_bio",
    "academic_qualifications",
    "professional_certificates",
    "services_offered",
)

_WRITABLE_STATUS = {
    TherapistProfileStatus.DRAFT,
    TherapistProfileStatus.PENDING,
    TherapistProfileStatus.APPROVED,
    TherapistProfileStatus.PAUSED,
}


def public_profile(profile: TherapistProfile, user: User | None = None) -> dict:
    account = user or profile.user
    status_value = profile.status.value if profile.status else TherapistProfileStatus.DRAFT.value
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "short_bio": profile.short_bio,
        "academic_qualifications": profile.academic_qualifications,
        "professional_certificates": list(profile.professional_certificates or []),
        "services_offered": list(profile.services_offered or []),
        "status": status_value,
        "email": account.email if account else None,
        "full_name": account.full_name if account else None,
    }


def _parse_status(raw: str | None, *, default: str) -> TherapistProfileStatus:
    label = (raw or default).strip().upper()
    try:
        status = TherapistProfileStatus(label)
    except ValueError as exc:
        raise ValidationError("Choose Draft, Pending, Approved, or Paused.") from exc
    if status not in _WRITABLE_STATUS:
        raise ValidationError("Choose Draft, Pending, Approved, or Paused.")
    return status


def list_profiles(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
    q: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    require_scope(principal, "profiles:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    page, page_size = normalize_pagination(page, page_size, settings.integration_max_page_size)
    stmt = (
        select(TherapistProfile)
        .join(User, TherapistProfile.user_id == User.id)
        .where(TherapistProfile.status != TherapistProfileStatus.DELETED)
        .order_by(func.lower(func.coalesce(TherapistProfile.display_name, User.full_name)), TherapistProfile.id)
    )
    if status:
        parsed = _parse_status(status, default="")
        stmt = stmt.where(TherapistProfile.status == parsed)
    search = (q or "").strip().lower()
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                func.lower(TherapistProfile.display_name).like(pattern),
                func.lower(User.full_name).like(pattern),
                func.lower(User.email).like(pattern),
            )
        )
    rows, total = paginate_query(db, stmt, page=page, page_size=page_size, max_page_size=settings.integration_max_page_size)
    items = [public_profile(row) for row in rows]
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.profiles_list",
        entity_type="therapist_profile",
        entity_id=None,
        new_value={"count": len(items), "status": status or ""},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return paginated_response(items, total, page, page_size)


def create_profile(
    db: Session,
    principal: IntegrationPrincipal,
    payload: dict,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    require_scope(principal, "profiles:write")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    user_id = payload.get("user_id")
    if not isinstance(user_id, int) or user_id < 1:
        raise ValidationError("Choose a therapist account before creating a profile.")
    target = db.get(User, user_id)
    if not target or not target.is_active:
        raise NotFoundError("Therapist account not found.")
    if RoleName.THERAPIST.value not in target.role_names:
        raise ValidationError("Choose a therapist account before creating a profile.")
    existing = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user_id)).first()
    if existing and existing.status != TherapistProfileStatus.DELETED and existing.deleted_at is None:
        raise ValidationError("A profile already exists for this therapist.")
    status = _parse_status(payload.get("status"), default="PENDING")
    profile = existing if existing else TherapistProfile(user_id=user_id)
    fields = {key: payload[key] for key in _LISTING_FIELDS if key in payload}
    try:
        profile_svc.apply_profile_fields(profile, fields, db)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Looks like we still need a few details before we can save this profile."
        raise ValidationError(detail) from exc
    profile.status = status
    profile.deleted_at = None
    if status == TherapistProfileStatus.APPROVED:
        profile.reviewed_at = datetime.now(timezone.utc)
        profile_svc.capture_approved_snapshot(profile)
    db.add(profile)
    db.flush()
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.profile_created",
        entity_type="therapist_profile",
        entity_id=profile.id,
        new_value={"user_id": user_id, "status": status.value},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return public_profile(profile, target)
