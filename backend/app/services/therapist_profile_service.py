from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.pagination import normalize_pagination, paginate_query
from app.core.permissions import RoleName
from app.core.therapist_services import get_service_categories, validate_service_ids
from app.core.timezone import today_ist
from app.models.daily_log import DailyLog
from app.models.role import Role
from app.models.session import Session as TherapySession
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import User
from app.services.reports_export_helpers import days_since
from app.services.therapist_profile_backfill_service import backfill_deleted_profiles_from_audit

NO_SESSIONS_INACTIVITY_DAYS = 15
NEEDS_LISTING_STATUS = "NEEDS_LISTING"


def _normalize_certs(certs: list[str] | None) -> list[str]:
    if not certs:
        return []
    return [c.strip() for c in certs if c and c.strip()]


# Therapist-editable listing fields reviewed before publish.
SNAPSHOT_FIELDS = (
    "display_name",
    "short_bio",
    "academic_qualifications",
    "professional_certificates",
    "services_offered",
)


def build_profile_snapshot(profile: TherapistProfile) -> dict:
    """Capture the therapist-editable fields that were just approved."""
    return {
        "display_name": profile.display_name,
        "short_bio": profile.short_bio,
        "academic_qualifications": profile.academic_qualifications,
        "professional_certificates": list(profile.professional_certificates or []),
        "services_offered": list(profile.services_offered or []),
    }


def build_submission_snapshot(data: dict, db: Session | None = None) -> dict:
    services = data.get("services_offered") or []
    if db is not None and services:
        try:
            services = validate_service_ids(services, db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "display_name": (data.get("display_name") or "").strip() or None,
        "short_bio": (data.get("short_bio") or "").strip() or None,
        "academic_qualifications": (data.get("academic_qualifications") or "").strip() or None,
        "professional_certificates": _normalize_certs(data.get("professional_certificates")),
        "services_offered": list(services),
    }


def capture_approved_snapshot(profile: TherapistProfile) -> None:
    """Store the current editable fields as the new approved baseline."""
    profile.approved_snapshot = build_profile_snapshot(profile)


def has_pending_submission(profile: TherapistProfile) -> bool:
    return bool(profile.pending_submission)


def apply_snapshot_to_profile(profile: TherapistProfile, snapshot: dict) -> None:
    for key in SNAPSHOT_FIELDS:
        if key not in snapshot:
            continue
        value = snapshot[key]
        if key in ("professional_certificates", "services_offered"):
            profile.__setattr__(key, list(value or []))
        else:
            profile.__setattr__(key, value)


def apply_pending_submission(profile: TherapistProfile) -> None:
    pending = profile.pending_submission
    if not pending:
        return
    apply_snapshot_to_profile(profile, pending)
    profile.pending_submission = None


def last_session_log_dates(db: Session, user_ids: list[int]) -> dict[int, datetime]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(TherapySession.therapist_user_id, func.max(DailyLog.submitted_at))
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.therapist_user_id.in_(user_ids),
            DailyLog.submitted_at.is_not(None),
        )
        .group_by(TherapySession.therapist_user_id)
    ).all()
    return {int(uid): ts for uid, ts in rows if uid is not None and ts is not None}


def inactive_therapist_user_ids(db: Session, *, days: int = NO_SESSIONS_INACTIVITY_DAYS) -> set[int]:
    cutoff = today_ist() - timedelta(days=days)
    listed_user_ids = {
        int(uid)
        for uid in db.scalars(
            select(TherapistProfile.user_id).where(TherapistProfile.status != TherapistProfileStatus.DELETED)
        ).all()
        if uid is not None
    }
    if not listed_user_ids:
        return set()

    last_logs = last_session_log_dates(db, list(listed_user_ids))
    inactive: set[int] = set()
    for uid in listed_user_ids:
        last_at = last_logs.get(uid)
        if last_at is None:
            inactive.add(uid)
            continue
        last_day = last_at.date() if hasattr(last_at, "date") else last_at
        if last_day < cutoff:
            inactive.add(uid)
    return inactive


def profile_to_dict(
    profile: TherapistProfile,
    user: User | None = None,
    *,
    last_session_log_at: datetime | None = None,
    days_since_last_session_log: int | None = None,
) -> dict:
    u = user or profile.user
    supervisor_name = None
    mentor_name = None
    if getattr(profile, "supervisor_user_id", None):
        sup = getattr(profile, "supervisor", None)
        if sup:
            supervisor_name = sup.full_name
    if getattr(profile, "mentor_user_id", None):
        men = getattr(profile, "mentor", None)
        if men:
            mentor_name = men.full_name
    status_value = profile.status.value if profile.status else TherapistProfileStatus.DRAFT.value
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "short_bio": profile.short_bio,
        "academic_qualifications": profile.academic_qualifications,
        "professional_certificates": profile.professional_certificates or [],
        "services_offered": profile.services_offered or [],
        "status": status_value,
        "admin_note": profile.admin_note,
        "submitted_at": profile.submitted_at,
        "reviewed_at": profile.reviewed_at,
        "deleted_at": profile.deleted_at,
        "email": u.email if u else None,
        "full_name": u.full_name if u else None,
        "supervisor_user_id": getattr(profile, "supervisor_user_id", None),
        "mentor_user_id": getattr(profile, "mentor_user_id", None),
        "supervisor_name": supervisor_name,
        "mentor_name": mentor_name,
        "employment_start_date": profile.employment_start_date,
        "leave_balance_year": profile.leave_balance_year,
        "leave_paid_days_backfill": int(profile.leave_paid_days_backfill or 0),
        "leave_carry_forward_days_backfill": int(profile.leave_carry_forward_days_backfill or 0),
        "leave_backfill_note": profile.leave_backfill_note,
        "approved_snapshot": profile.approved_snapshot,
        "pending_submission": profile.pending_submission,
        "has_pending_changes": has_pending_submission(profile),
        "last_session_log_at": last_session_log_at,
        "days_since_last_session_log": days_since_last_session_log,
        "tds_rate_percent": float(profile.tds_rate_percent)
        if profile.tds_rate_percent is not None
        else None,
    }


def needs_listing_to_dict(user: User) -> dict:
    return {
        "id": None,
        "user_id": user.id,
        "display_name": user.full_name,
        "short_bio": None,
        "academic_qualifications": None,
        "professional_certificates": [],
        "services_offered": [],
        "status": NEEDS_LISTING_STATUS,
        "admin_note": None,
        "submitted_at": None,
        "reviewed_at": None,
        "deleted_at": None,
        "email": user.email,
        "full_name": user.full_name,
        "supervisor_user_id": None,
        "mentor_user_id": None,
        "supervisor_name": None,
        "mentor_name": None,
        "employment_start_date": None,
        "leave_balance_year": None,
        "leave_paid_days_backfill": 0,
        "leave_carry_forward_days_backfill": 0,
        "leave_backfill_note": None,
        "approved_snapshot": None,
        "pending_submission": None,
        "has_pending_changes": False,
        "last_session_log_at": None,
        "days_since_last_session_log": None,
    }


def enrich_profile_dicts(db: Session, items: list[dict]) -> list[dict]:
    user_ids = [int(item["user_id"]) for item in items if item.get("user_id")]
    last_logs = last_session_log_dates(db, user_ids)
    today = today_ist()
    for item in items:
        uid = item.get("user_id")
        last_at = last_logs.get(int(uid)) if uid is not None else None
        item["last_session_log_at"] = last_at
        if last_at is None:
            item["days_since_last_session_log"] = None
        else:
            last_day = last_at.date() if hasattr(last_at, "date") else last_at
            item["days_since_last_session_log"] = days_since(last_day, as_of=today)
    return items


def get_or_create_profile(db: Session, user_id: int) -> TherapistProfile:
    profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user_id)).first()
    if profile:
        return profile
    profile = TherapistProfile(user_id=user_id, status=TherapistProfileStatus.DRAFT)
    db.add(profile)
    db.flush()
    return profile


def _validate_staff_user_id(db: Session, user_id: int | None, *, field_label: str) -> None:
    if user_id is None:
        return
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail=f"Selected {field_label} is not available. Refresh and try again.")


def apply_profile_fields(profile: TherapistProfile, data: dict, db: Session | None = None) -> None:
    if "display_name" in data:
        profile.display_name = data["display_name"]
    if "short_bio" in data:
        profile.short_bio = data["short_bio"]
    if "academic_qualifications" in data:
        profile.academic_qualifications = data["academic_qualifications"]
    if "professional_certificates" in data:
        profile.professional_certificates = _normalize_certs(data["professional_certificates"])
    if "services_offered" in data:
        try:
            profile.services_offered = validate_service_ids(data["services_offered"] or [], db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if "supervisor_user_id" in data:
        new_cm = data["supervisor_user_id"]
        if db is not None:
            _validate_staff_user_id(db, new_cm, field_label="case manager")
        profile.supervisor_user_id = new_cm
        if new_cm and db is not None:
            from app.services.assignment_service import sync_case_managers_for_therapist

            sync_case_managers_for_therapist(db, profile.user_id, new_cm)
    if "mentor_user_id" in data:
        if db is not None:
            from app.services.mentor_scope_service import validate_mentor_is_case_manager

            validate_mentor_is_case_manager(db, data["mentor_user_id"])
        profile.mentor_user_id = data["mentor_user_id"]
    if "employment_start_date" in data:
        profile.employment_start_date = data["employment_start_date"]
    if "leave_balance_year" in data:
        profile.leave_balance_year = data["leave_balance_year"]
    if "leave_paid_days_backfill" in data:
        profile.leave_paid_days_backfill = int(data["leave_paid_days_backfill"] or 0)
    if "leave_carry_forward_days_backfill" in data:
        profile.leave_carry_forward_days_backfill = int(data["leave_carry_forward_days_backfill"] or 0)
    if "leave_backfill_note" in data:
        profile.leave_backfill_note = (data["leave_backfill_note"] or "").strip() or None
    if "tds_rate_percent" in data:
        rate = data["tds_rate_percent"]
        profile.tds_rate_percent = None if rate is None else float(rate)


def apply_leave_backfill(
    profile: TherapistProfile,
    *,
    year: int,
    paid_backfill: int,
    carry_backfill: int,
    note: Optional[str],
    employment_start_date: Optional[date],
    actor_user_id: int,
) -> None:
    if paid_backfill < 0 or carry_backfill < 0:
        raise HTTPException(status_code=400, detail="Backfill days cannot be negative")
    if (paid_backfill > 0 or carry_backfill > 0) and not (note or "").strip():
        raise HTTPException(status_code=400, detail="Note is required when backfill days are set")
    profile.leave_balance_year = year
    profile.leave_paid_days_backfill = paid_backfill
    profile.leave_carry_forward_days_backfill = carry_backfill
    profile.leave_backfill_note = (note or "").strip() or None
    if employment_start_date is not None:
        profile.employment_start_date = employment_start_date
    profile.leave_backfill_updated_at = datetime.now(timezone.utc)
    profile.leave_backfill_updated_by_user_id = actor_user_id


def _validate_submission_payload(data: dict, user: User, db: Session) -> dict:
    submission = build_submission_snapshot(data, db)
    if not submission["services_offered"]:
        raise HTTPException(status_code=400, detail="Select at least one service you offer")
    if not (submission["display_name"] or user.full_name):
        raise HTTPException(status_code=400, detail="Display name is required")
    return submission


def therapist_submit_profile(db: Session, user: User, data: dict) -> TherapistProfile:
    if RoleName.THERAPIST.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Therapist access only")
    profile = get_or_create_profile(db, user.id)
    if profile.status == TherapistProfileStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Profile is paused")
    if profile.status == TherapistProfileStatus.DELETED:
        raise HTTPException(
            status_code=400,
            detail="This service listing was removed. Contact your case manager to restore it.",
        )

    submission = _validate_submission_payload(data, user, db)
    if not submission["display_name"]:
        submission["display_name"] = user.full_name

    operational = {}
    if "employment_start_date" in data:
        operational["employment_start_date"] = data["employment_start_date"] or None

    if profile.approved_snapshot:
        profile.pending_submission = submission
        apply_snapshot_to_profile(profile, profile.approved_snapshot)
        if operational:
            apply_profile_fields(profile, operational, db)
        profile.status = TherapistProfileStatus.APPROVED
    else:
        apply_profile_fields(profile, {**submission, **operational}, db)
        profile.status = TherapistProfileStatus.PENDING
        profile.pending_submission = None

    profile.submitted_at = datetime.now(timezone.utc)
    profile.admin_note = None
    db.flush()
    return profile


def admin_approve_profile(profile: TherapistProfile, admin_note: str | None = None) -> None:
    if profile.pending_submission:
        apply_pending_submission(profile)
    profile.status = TherapistProfileStatus.APPROVED
    if admin_note:
        profile.admin_note = admin_note
    capture_approved_snapshot(profile)


def soft_delete_profile(profile: TherapistProfile) -> None:
    profile.status = TherapistProfileStatus.DELETED
    profile.deleted_at = datetime.now(timezone.utc)


def restore_profile(profile: TherapistProfile) -> None:
    profile.status = TherapistProfileStatus.PAUSED
    profile.deleted_at = None


def list_active_profiles(db: Session) -> list[TherapistProfile]:
    return list(
        db.scalars(
            select(TherapistProfile)
            .where(TherapistProfile.status != TherapistProfileStatus.DELETED)
            .order_by(TherapistProfile.updated_at.desc())
        ).all()
    )


def _apply_profile_status_filter(stmt, status: TherapistProfileStatus | str | None):
    if status == TherapistProfileStatus.PENDING:
        return stmt.where(
            TherapistProfile.status != TherapistProfileStatus.DELETED,
            or_(
                TherapistProfile.status == TherapistProfileStatus.PENDING,
                TherapistProfile.pending_submission.isnot(None),
            ),
        )
    if status == TherapistProfileStatus.APPROVED:
        return stmt.where(
            TherapistProfile.status == TherapistProfileStatus.APPROVED,
            TherapistProfile.pending_submission.is_(None),
        )
    if status == TherapistProfileStatus.DELETED:
        return stmt.where(TherapistProfile.status == TherapistProfileStatus.DELETED)
    if status and status != TherapistProfileStatus.DELETED:
        return stmt.where(TherapistProfile.status == status)
    return stmt.where(TherapistProfile.status != TherapistProfileStatus.DELETED)


def _profiles_list_stmt(
    db: Session,
    status: TherapistProfileStatus | str | None = None,
    *,
    activity: str | None = None,
    search: str | None = None,
    user_id: int | None = None,
    user_ids: list[int] | None = None,
):
    if status == NEEDS_LISTING_STATUS:
        return None

    if status == TherapistProfileStatus.DELETED:
        backfill_deleted_profiles_from_audit(db)

    stmt = (
        select(TherapistProfile)
        .options(
            joinedload(TherapistProfile.user),
            joinedload(TherapistProfile.supervisor),
            joinedload(TherapistProfile.mentor),
        )
        .order_by(TherapistProfile.updated_at.desc())
    )
    stmt = _apply_profile_status_filter(stmt, status)

    if activity == "no_sessions_15d":
        inactive_ids = inactive_therapist_user_ids(db)
        if not inactive_ids:
            stmt = stmt.where(TherapistProfile.id == -1)
        else:
            stmt = stmt.where(TherapistProfile.user_id.in_(inactive_ids))

    if user_id is not None:
        stmt = stmt.where(TherapistProfile.user_id == user_id)
    if user_ids:
        stmt = stmt.where(TherapistProfile.user_id.in_(user_ids))

    q = (search or "").strip().lower()
    if q:
        pattern = f"%{q}%"
        user_match = select(User.id).where(
            or_(
                func.lower(User.email).like(pattern),
                func.lower(User.full_name).like(pattern),
            )
        )
        stmt = stmt.where(
            or_(
                TherapistProfile.user_id.in_(user_match),
                func.lower(TherapistProfile.display_name).like(pattern),
            )
        )
    return stmt


def _needs_listing_stmt(
    db: Session,
    *,
    search: str | None = None,
    user_id: int | None = None,
    user_ids: list[int] | None = None,
):
    therapist_role_ids = select(User.id).join(User.roles).where(
        Role.name == RoleName.THERAPIST.value,
        User.is_active.is_(True),
    )
    profile_user_ids = select(TherapistProfile.user_id)
    stmt = (
        select(User)
        .where(User.id.in_(therapist_role_ids))
        .where(User.id.not_in(profile_user_ids))
        .order_by(User.full_name.asc(), User.email.asc())
    )
    if user_id is not None:
        stmt = stmt.where(User.id == user_id)
    if user_ids:
        stmt = stmt.where(User.id.in_(user_ids))
    q = (search or "").strip().lower()
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                func.lower(User.email).like(pattern),
                func.lower(User.full_name).like(pattern),
            )
        )
    return stmt


def paginate_profile_listings(
    db: Session,
    *,
    status: TherapistProfileStatus | str | None = None,
    activity: str | None = None,
    search: str | None = None,
    user_id: int | None = None,
    user_ids: list[int] | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    page, page_size = normalize_pagination(page, page_size)

    if status == NEEDS_LISTING_STATUS:
        stmt = _needs_listing_stmt(db, search=search, user_id=user_id, user_ids=user_ids)
        users, total = paginate_query(db, stmt, page=page, page_size=page_size)
        items = [needs_listing_to_dict(u) for u in users]
        return enrich_profile_dicts(db, items), total

    stmt = _profiles_list_stmt(
        db,
        status,
        activity=activity,
        search=search,
        user_id=user_id,
        user_ids=user_ids,
    )
    profiles, total = paginate_query(db, stmt, page=page, page_size=page_size)
    items = [profile_to_dict(p, p.user) for p in profiles]
    return enrich_profile_dicts(db, items), total


def list_profiles(
    db: Session,
    status: TherapistProfileStatus | str | None = None,
    *,
    activity: str | None = None,
) -> list[TherapistProfile]:
    stmt = _profiles_list_stmt(db, status, activity=activity)
    if stmt is None:
        return []
    return list(db.scalars(stmt).all())


def list_needs_listing_users(db: Session) -> list[User]:
    stmt = _needs_listing_stmt(db)
    return list(db.scalars(stmt).all())


def profile_summary_counts(db: Session, profiles: list[TherapistProfile] | None = None) -> dict[str, int]:
    if profiles is None:
        profiles = list_active_profiles(db)
    counts = {"PENDING": 0, "DRAFT": 0, "APPROVED": 0, "PAUSED": 0, "DELETED": 0}
    for profile in profiles:
        if has_pending_submission(profile):
            counts["PENDING"] += 1
            continue
        key = profile.status.value if hasattr(profile.status, "value") else str(profile.status)
        if key in counts:
            counts[key] += 1

    deleted_extra = db.scalar(
        select(func.count())
        .select_from(TherapistProfile)
        .where(TherapistProfile.status == TherapistProfileStatus.DELETED)
    )
    counts["DELETED"] = int(deleted_extra or 0)

    therapists = db.scalars(select(User.id).join(User.roles).where(Role.name == RoleName.THERAPIST.value)).all()
    profile_user_ids = set(db.scalars(select(TherapistProfile.user_id)).all())
    counts["needs_listing"] = len(set(therapists) - profile_user_ids)
    counts["no_sessions_15d"] = len(inactive_therapist_user_ids(db))
    counts["total"] = len(profiles)
    return counts


def service_categories(db: Session) -> list[dict[str, str]]:
    return get_service_categories(db)
