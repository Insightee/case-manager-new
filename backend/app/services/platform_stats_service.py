from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import RoleName, user_has_permission
from app.core.timezone import IST, now_ist, today_ist
from app.models.app_usage_chunk import AppUsageChunk
from app.models.audit_event import AuditEvent
from app.models.user import User

ACTIVE_NOW_MINUTES = 15
ACTIVITY_STATUS_ALL = "all"
ACTIVITY_STATUS_ACTIVE_NOW = "active_now"
ACTIVITY_STATUS_LOGGED_IN = "logged_in"
ACTIVITY_STATUS_ACTIVE = "active"
ACTIVITY_STATUS_VALUES = frozenset(
    {
        ACTIVITY_STATUS_ALL,
        ACTIVITY_STATUS_ACTIVE_NOW,
        ACTIVITY_STATUS_LOGGED_IN,
        ACTIVITY_STATUS_ACTIVE,
    }
)

PLATFORM_ROLE_PRIORITY: tuple[RoleName, ...] = (
    RoleName.SUPER_ADMIN,
    RoleName.MODULE_ADMIN,
    RoleName.FINANCE,
    RoleName.HR,
    RoleName.SUPERVISOR,
    RoleName.CASE_MANAGER,
    RoleName.ADMIN,
    RoleName.THERAPIST,
    RoleName.PARENT,
    RoleName.SCHOOL_COORDINATOR,
    RoleName.VIEWER,
)


def resolve_platform_primary_role(role_names: list[str] | None) -> str:
    names = set(role_names or [])
    for role in PLATFORM_ROLE_PRIORITY:
        if role.value in names:
            return role.value
    return role_names[0] if role_names else "UNKNOWN"


def _period_bounds_ist(days: int) -> tuple[datetime, datetime, str]:
    end_local = now_ist()
    day_count = max(1, min(days, 90))
    start_date = end_local.date() - timedelta(days=day_count - 1)
    start_local = datetime.combine(start_date, time.min, tzinfo=IST)
    label = "today" if day_count == 1 else f"last_{day_count}_days"
    return start_local, end_local, label


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _load_users(db: Session, user_ids: set[int]) -> dict[int, User]:
    if not user_ids:
        return {}
    rows = db.scalars(
        select(User).options(selectinload(User.roles)).where(User.id.in_(user_ids))
    ).all()
    return {u.id: u for u in rows}


@dataclass
class PeriodActivitySnapshot:
    start_local: datetime
    end_local: datetime
    period_label: str
    start_utc: datetime
    end_utc: datetime
    active_cutoff: datetime
    login_by_user: dict[int, dict[str, Any]]
    usage_by_user: dict[int, dict[str, Any]]
    active_now_ids: set[int]
    by_portal: dict[str, dict[str, Any]]


def _collect_period_activity(db: Session, *, days: int) -> PeriodActivitySnapshot:
    start_local, end_local, period_label = _period_bounds_ist(days)
    start_utc = _to_utc(start_local)
    end_utc = _to_utc(end_local)
    active_cutoff = datetime.now(timezone.utc) - timedelta(minutes=ACTIVE_NOW_MINUTES)

    login_rows = db.execute(
        select(
            AuditEvent.actor_user_id,
            func.count(AuditEvent.id),
            func.max(AuditEvent.created_at),
        )
        .where(
            AuditEvent.action == "login",
            AuditEvent.actor_user_id.isnot(None),
            AuditEvent.created_at >= start_utc,
            AuditEvent.created_at <= end_utc,
        )
        .group_by(AuditEvent.actor_user_id)
    ).all()

    login_by_user: dict[int, dict[str, Any]] = {}
    for actor_id, login_count, last_login_at in login_rows:
        if not actor_id:
            continue
        login_by_user[int(actor_id)] = {
            "login_count": int(login_count or 0),
            "last_login_at": last_login_at,
        }

    usage_rows = db.execute(
        select(
            AppUsageChunk.actor_user_id,
            AppUsageChunk.portal,
            func.sum(AppUsageChunk.active_seconds),
            func.max(AppUsageChunk.chunk_ended_at),
        )
        .where(
            AppUsageChunk.chunk_ended_at.isnot(None),
            AppUsageChunk.chunk_ended_at >= start_utc,
            AppUsageChunk.chunk_ended_at <= end_utc,
        )
        .group_by(AppUsageChunk.actor_user_id, AppUsageChunk.portal)
    ).all()

    usage_by_user: dict[int, dict[str, Any]] = {}
    by_portal: dict[str, dict[str, Any]] = {}
    for actor_id, portal, active_seconds, last_seen_at in usage_rows:
        if not actor_id:
            continue
        uid = int(actor_id)
        seconds = int(active_seconds or 0)
        portal_key = portal or "unknown"
        bucket = usage_by_user.setdefault(
            uid,
            {"active_seconds": 0, "last_seen_at": None, "portals": set()},
        )
        bucket["active_seconds"] += seconds
        bucket["portals"].add(portal_key)
        if last_seen_at and (
            bucket["last_seen_at"] is None or last_seen_at > bucket["last_seen_at"]
        ):
            bucket["last_seen_at"] = last_seen_at

        portal_bucket = by_portal.setdefault(
            portal_key,
            {"portal": portal_key, "unique_users": set(), "active_seconds": 0, "active_now": 0},
        )
        portal_bucket["unique_users"].add(uid)
        portal_bucket["active_seconds"] += seconds

    active_now_rows = db.execute(
        select(AppUsageChunk.actor_user_id, AppUsageChunk.portal)
        .where(
            AppUsageChunk.chunk_ended_at.isnot(None),
            AppUsageChunk.chunk_ended_at >= active_cutoff,
        )
        .distinct()
    ).all()
    active_now_ids: set[int] = set()
    for actor_id, portal in active_now_rows:
        if not actor_id:
            continue
        uid = int(actor_id)
        active_now_ids.add(uid)
        portal_key = portal or "unknown"
        portal_bucket = by_portal.setdefault(
            portal_key,
            {"portal": portal_key, "unique_users": set(), "active_seconds": 0, "active_now": 0},
        )
        portal_bucket["active_now"] += 1

    return PeriodActivitySnapshot(
        start_local=start_local,
        end_local=end_local,
        period_label=period_label,
        start_utc=start_utc,
        end_utc=end_utc,
        active_cutoff=active_cutoff,
        login_by_user=login_by_user,
        usage_by_user=usage_by_user,
        active_now_ids=active_now_ids,
        by_portal=by_portal,
    )


def _serialize_activity_row(
    uid: int,
    users: dict[int, User],
    snapshot: PeriodActivitySnapshot,
) -> dict[str, Any]:
    u = users.get(uid)
    primary_role = resolve_platform_primary_role(u.role_names if u else None)
    login_meta = snapshot.login_by_user.get(uid, {})
    usage_meta = snapshot.usage_by_user.get(uid, {})
    last_login_at = login_meta.get("last_login_at")
    last_seen_at = usage_meta.get("last_seen_at")
    last_activity_at = last_seen_at or last_login_at
    return {
        "user_id": uid,
        "user_name": u.full_name if u else None,
        "user_email": u.email if u else None,
        "primary_role": primary_role,
        "logged_in_period": uid in snapshot.login_by_user,
        "login_count": int(login_meta.get("login_count") or 0),
        "active_seconds": int(usage_meta.get("active_seconds") or 0),
        "last_login_at": _iso(last_login_at),
        "last_seen_at": _iso(last_seen_at),
        "last_activity_at": _iso(last_activity_at),
        "active_now": uid in snapshot.active_now_ids,
        "portals": sorted(usage_meta.get("portals") or []),
    }


def _aggregate_by_role(snapshot: PeriodActivitySnapshot, users: dict[int, User]) -> list[dict[str, Any]]:
    all_user_ids = set(snapshot.login_by_user) | set(snapshot.usage_by_user) | snapshot.active_now_ids
    by_role: dict[str, dict[str, Any]] = {}
    for uid in all_user_ids:
        u = users.get(uid)
        primary_role = resolve_platform_primary_role(u.role_names if u else None)
        usage_meta = snapshot.usage_by_user.get(uid, {})
        role_bucket = by_role.setdefault(
            primary_role,
            {
                "role": primary_role,
                "unique_logins": 0,
                "unique_active": 0,
                "active_now": 0,
                "active_seconds": 0,
            },
        )
        if uid in snapshot.login_by_user:
            role_bucket["unique_logins"] += 1
        if uid in snapshot.usage_by_user:
            role_bucket["unique_active"] += 1
            role_bucket["active_seconds"] += int(usage_meta.get("active_seconds") or 0)
        if uid in snapshot.active_now_ids:
            role_bucket["active_now"] += 1
    return sorted(
        by_role.values(),
        key=lambda row: (row["unique_logins"], row["unique_active"]),
        reverse=True,
    )


def _matches_search(row: dict[str, Any], query: str | None) -> bool:
    needle = (query or "").strip().lower()
    if not needle:
        return True
    name = (row.get("user_name") or "").lower()
    email = (row.get("user_email") or "").lower()
    return needle in name or needle in email


def _matches_status(row: dict[str, Any], status: str) -> bool:
    if status == ACTIVITY_STATUS_ALL:
        return True
    if status == ACTIVITY_STATUS_ACTIVE_NOW:
        return bool(row.get("active_now"))
    if status == ACTIVITY_STATUS_LOGGED_IN:
        return bool(row.get("logged_in_period"))
    if status == ACTIVITY_STATUS_ACTIVE:
        return int(row.get("active_seconds") or 0) > 0
    return True


def _matches_role(row: dict[str, Any], role: str | None) -> bool:
    if not role:
        return True
    return (row.get("primary_role") or "").upper() == role.strip().upper()


def _matches_portal(row: dict[str, Any], portal: str | None) -> bool:
    if not portal:
        return True
    return portal.strip().lower() in (row.get("portals") or [])


def build_platform_stats(db: Session, user: User, *, days: int = 1) -> dict[str, Any]:
    if not user_has_permission(user, "admin.override"):
        raise PermissionError("Super admin permission required")

    snapshot = _collect_period_activity(db, days=days)
    all_user_ids = set(snapshot.login_by_user) | set(snapshot.usage_by_user) | snapshot.active_now_ids
    users = _load_users(db, all_user_ids)

    portal_items = []
    for portal_key in sorted(snapshot.by_portal):
        bucket = snapshot.by_portal[portal_key]
        portal_items.append(
            {
                "portal": bucket["portal"],
                "unique_users": len(bucket["unique_users"]),
                "active_seconds": int(bucket["active_seconds"]),
                "active_now": int(bucket["active_now"]),
            }
        )

    total_active_seconds = sum(
        int(u.get("active_seconds") or 0) for u in snapshot.usage_by_user.values()
    )
    total_users = db.scalar(select(func.count(User.id))) or 0

    return {
        "timezone": "Asia/Kolkata",
        "period": {
            "label": snapshot.period_label,
            "days": max(1, min(days, 90)),
            "start_at": _iso(snapshot.start_local),
            "end_at": _iso(snapshot.end_local),
            "calendar_date": today_ist().isoformat() if days <= 1 else None,
        },
        "summary": {
            "total_users": int(total_users),
            "unique_logins": len(snapshot.login_by_user),
            "login_events": sum(
                int(v.get("login_count") or 0) for v in snapshot.login_by_user.values()
            ),
            "unique_active_users": len(snapshot.usage_by_user),
            "active_now": len(snapshot.active_now_ids),
            "total_active_seconds": total_active_seconds,
            "active_now_window_minutes": ACTIVE_NOW_MINUTES,
        },
        "by_portal": portal_items,
        "by_role": _aggregate_by_role(snapshot, users),
        "tracking": {
            "usage_heartbeats_enabled": True,
            "active_now_source": "app_usage_chunks",
            "note": (
                "Active time and “active now” come from portal usage heartbeats. "
                "Logins are recorded on every successful sign-in."
            ),
        },
    }


def list_platform_activity(
    db: Session,
    user: User,
    *,
    days: int = 1,
    q: str | None = None,
    status: str = ACTIVITY_STATUS_ALL,
    role: str | None = None,
    portal: str | None = None,
    page: int = 1,
    limit: int = 25,
) -> dict[str, Any]:
    if not user_has_permission(user, "admin.override"):
        raise PermissionError("Super admin permission required")

    normalized_status = (status or ACTIVITY_STATUS_ALL).strip().lower()
    if normalized_status not in ACTIVITY_STATUS_VALUES:
        raise ValueError(
            f"status must be one of: {', '.join(sorted(ACTIVITY_STATUS_VALUES))}"
        )

    page_num = max(1, page)
    page_size = max(1, min(limit, 100))

    snapshot = _collect_period_activity(db, days=days)
    all_user_ids = set(snapshot.login_by_user) | set(snapshot.usage_by_user) | snapshot.active_now_ids
    users = _load_users(db, all_user_ids)

    rows = [
        _serialize_activity_row(uid, users, snapshot)
        for uid in all_user_ids
    ]
    rows.sort(key=lambda row: row.get("last_activity_at") or "", reverse=True)

    filtered = [
        row
        for row in rows
        if _matches_search(row, q)
        and _matches_status(row, normalized_status)
        and _matches_role(row, role)
        and _matches_portal(row, portal)
    ]

    total = len(filtered)
    start_idx = (page_num - 1) * page_size
    end_idx = start_idx + page_size
    items = filtered[start_idx:end_idx]
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 0

    return {
        "timezone": "Asia/Kolkata",
        "period": {
            "label": snapshot.period_label,
            "days": max(1, min(days, 90)),
            "start_at": _iso(snapshot.start_local),
            "end_at": _iso(snapshot.end_local),
        },
        "filters": {
            "q": (q or "").strip() or None,
            "status": normalized_status,
            "role": role.strip().upper() if role else None,
            "portal": portal.strip().lower() if portal else None,
        },
        "items": items,
        "page": page_num,
        "limit": page_size,
        "total": total,
        "total_pages": total_pages,
        "range_start": start_idx + 1 if total else 0,
        "range_end": min(end_idx, total) if total else 0,
    }
