"""Therapist attention drill-down. Live SQL; login is not app activity."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.billing_month import today_ist
from app.core.permissions import user_has_permission
from app.models.app_usage_chunk import AppUsageChunk
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.audit_event import AuditEvent
from app.models.daily_log import DailyLog
from app.models.role import Role
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import EmploymentStatus, User
from app.services.therapist_profile_quality import evaluate_profile_quality


def can_view_therapist_attention(user: User) -> bool:
    return (
        user_has_permission(user, "user.manage")
        or user_has_permission(user, "admin.override")
        or user_has_permission(user, "case.read.all")
    )


def _last_map(db: Session, stmt) -> dict[int, object]:
    return {int(uid): value for uid, value in db.execute(stmt).all() if uid is not None}


def list_therapist_attention(
    db: Session,
    user: User,
    *,
    page: int = 1,
    page_size: int = 50,
    window_days: int = 14,
) -> dict:
    del user  # scope is organisation therapists; caller already authorised
    today = today_ist()
    cutoff = today - timedelta(days=max(1, int(window_days)))
    log_cutoff = today - timedelta(days=2)

    therapists = list(
        db.scalars(
            select(User)
            .join(User.roles)
            .where(Role.name == "THERAPIST")
            .order_by(User.full_name.asc())
        ).unique().all()
    )
    ids = [t.id for t in therapists]
    if not ids:
        return {
            "rows": [],
            "count": 0,
            "page": page,
            "pageSize": page_size,
            "windowDays": window_days,
            "asOf": today.isoformat(),
            "loginNote": "No recorded login is not the same as never used.",
        }

    last_login = _last_map(
        db,
        select(AuditEvent.actor_user_id, func.max(AuditEvent.created_at)).where(
            AuditEvent.action == "login",
            AuditEvent.actor_user_id.in_(ids),
        ).group_by(AuditEvent.actor_user_id),
    )
    last_usage = _last_map(
        db,
        select(AppUsageChunk.actor_user_id, func.max(AppUsageChunk.chunk_ended_at)).where(
            AppUsageChunk.actor_user_id.in_(ids)
        ).group_by(AppUsageChunk.actor_user_id),
    )
    last_completed = _last_map(
        db,
        select(TherapySession.therapist_user_id, func.max(TherapySession.scheduled_date)).where(
            TherapySession.therapist_user_id.in_(ids),
            TherapySession.status == SessionStatus.COMPLETED,
        ).group_by(TherapySession.therapist_user_id),
    )
    last_log = _last_map(
        db,
        select(TherapySession.therapist_user_id, func.max(DailyLog.submitted_at))
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(TherapySession.therapist_user_id.in_(ids), DailyLog.submitted_at.is_not(None))
        .group_by(TherapySession.therapist_user_id),
    )
    missing_logs = dict(
        db.execute(
            select(TherapySession.therapist_user_id, func.count(TherapySession.id))
            .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.therapist_user_id.in_(ids),
                TherapySession.status == SessionStatus.COMPLETED,
                TherapySession.scheduled_date <= log_cutoff,
                DailyLog.id.is_(None),
            )
            .group_by(TherapySession.therapist_user_id)
        ).all()
    )
    active_assignments = dict(
        db.execute(
            select(CaseAssignment.therapist_user_id, func.count(CaseAssignment.id)).where(
                CaseAssignment.therapist_user_id.in_(ids),
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            ).group_by(CaseAssignment.therapist_user_id)
        ).all()
    )
    profiles = {
        p.user_id: p
        for p in db.scalars(select(TherapistProfile).where(TherapistProfile.user_id.in_(ids))).all()
    }

    rows = []
    for therapist in therapists:
        profile = profiles.get(therapist.id)
        quality = evaluate_profile_quality(therapist, profile)
        missing_fields = [item["key"] for item in quality.get("items") or [] if not item.get("passed")]
        login_at = last_login.get(therapist.id)
        usage_at = last_usage.get(therapist.id)
        gaps = []
        if therapist.id not in last_login:
            gaps.append("no_recorded_login")
        if int(missing_logs.get(therapist.id) or 0) > 0:
            gaps.append("completed_sessions_missing_logs")
        if profile and profile.status in (TherapistProfileStatus.PENDING, TherapistProfileStatus.CHANGES_REQUESTED):
            gaps.append("pending_profile")
        if not therapist.is_active or therapist.employment_status != EmploymentStatus.ACTIVE:
            if int(active_assignments.get(therapist.id) or 0) > 0:
                gaps.append("inactive_with_assignment")
        if missing_fields:
            gaps.append("missing_listing_fields")
        last_session = last_completed.get(therapist.id)
        if last_session and last_session < cutoff and therapist.is_active:
            gaps.append("activity_gap_requiring_review")

        emp = therapist.employment_status
        rows.append(
            {
                "userId": therapist.id,
                "fullName": therapist.full_name,
                "email": therapist.email,
                "accountActive": bool(therapist.is_active),
                "employmentStatus": emp.value if hasattr(emp, "value") else str(emp or ""),
                "activeAssignmentCount": int(active_assignments.get(therapist.id) or 0),
                "lastLoginAt": login_at.isoformat() if login_at else None,
                "lastAppActivityAt": usage_at.isoformat() if usage_at else None,
                "lastCompletedSessionDate": last_session.isoformat() if last_session else None,
                "lastLogSubmittedAt": last_log.get(therapist.id).isoformat() if last_log.get(therapist.id) else None,
                "completedSessionsMissingLogs": int(missing_logs.get(therapist.id) or 0),
                "profileStatus": profile.status.value if profile and profile.status else "NONE",
                "pendingProfileChanges": bool(profile and profile.pending_submission),
                "missingRequiredFields": missing_fields,
                "listingScore": quality.get("score"),
                "gaps": gaps,
                "href": f"/admin/therapist-profiles?userId={therapist.id}",
            }
        )

    rows.sort(key=lambda r: (0 if r["gaps"] else 1, -r["completedSessionsMissingLogs"], r["fullName"]))
    total = len(rows)
    start = (max(page, 1) - 1) * page_size
    page_rows = rows[start : start + page_size]
    return {
        "rows": page_rows,
        "count": total,
        "page": page,
        "pageSize": page_size,
        "previewLimited": len(page_rows) < total,
        "windowDays": window_days,
        "asOf": today.isoformat(),
        "loginNote": "No recorded login is not the same as never used. Last app activity is from in-app usage, not login.",
    }
