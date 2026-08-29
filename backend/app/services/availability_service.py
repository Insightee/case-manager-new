from __future__ import annotations

import base64
import hashlib
import json
import secrets
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_redis
from app.core.timezone import now_ist, today_ist
from app.models.calendar_availability import (
    AvailabilityExceptionType,
    CalendarProvider,
    StaffAvailabilityException,
    StaffAvailabilityRule,
    StaffBookingPolicy,
    UserCalendarConnection,
)
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus
from app.models.session import Session as TherapySession, SessionStatus
from app.models.user import User
from app.services.cm_meeting_service import meeting_participant_user_ids

IST = ZoneInfo("Asia/Kolkata")
GOOGLE_FREEBUSY_SCOPE = "https://www.googleapis.com/auth/calendar.freebusy"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
GOOGLE_CACHE_TTL_SECONDS = 600
DEFAULT_OPEN_WINDOWS: dict[int, list[tuple[time, time]]] = {
    0: [(time(10, 0), time(19, 0))],
    1: [(time(10, 0), time(19, 0))],
    2: [(time(10, 0), time(19, 0))],
    3: [(time(10, 0), time(19, 0))],
    4: [(time(10, 0), time(19, 0))],
}
DEFAULT_ALLOWED_DURATIONS = [30, 45, 60, 90]

_MEMORY_CACHE: dict[str, tuple[float, str]] = {}


def _normalize_user_ids(user_ids: list[int | str] | tuple[int | str, ...]) -> list[int]:
    clean = sorted({int(uid) for uid in user_ids if str(uid).strip()})
    return clean


def _redis_cache_key(key: str) -> str:
    return f"calendar:freebusy:{key}"


def _cache_get(key: str) -> Any | None:
    try:
        redis_client = get_redis()
    except RuntimeError:
        redis_client = None
    if redis_client is not None:
        raw = redis_client.get(_redis_cache_key(key))
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    entry = _MEMORY_CACHE.get(key)
    if not entry:
        return None
    expires_at, payload = entry
    if expires_at < datetime.now(timezone.utc).timestamp():
        _MEMORY_CACHE.pop(key, None)
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _cache_set(key: str, payload: Any, ttl_seconds: int = GOOGLE_CACHE_TTL_SECONDS) -> None:
    serialized = json.dumps(payload, default=str)
    try:
        redis_client = get_redis()
    except RuntimeError:
        redis_client = None
    if redis_client is not None:
        redis_client.setex(_redis_cache_key(key), ttl_seconds, serialized)
        return
    _MEMORY_CACHE[key] = (datetime.now(timezone.utc).timestamp() + ttl_seconds, serialized)


def _fernet() -> Fernet:
    seed = (settings.jwt_secret_key or settings.integration_jwt_secret_key or "insighte-case-calendar").encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    return Fernet(key)


def _encrypt(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None


def _aware(day: date, wall_time: time) -> datetime:
    return datetime.combine(day, wall_time).replace(tzinfo=IST)


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _localize(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def _merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    clean = sorted((start, end) for start, end in intervals if end > start)
    if not clean:
        return []
    merged: list[tuple[datetime, datetime]] = [clean[0]]
    for start, end in clean[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _intersect_intervals(
    left: list[tuple[datetime, datetime]],
    right: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not left or not right:
        return []
    result: list[tuple[datetime, datetime]] = []
    li = ri = 0
    left_sorted = _merge_intervals(left)
    right_sorted = _merge_intervals(right)
    while li < len(left_sorted) and ri < len(right_sorted):
        start = max(left_sorted[li][0], right_sorted[ri][0])
        end = min(left_sorted[li][1], right_sorted[ri][1])
        if end > start:
            result.append((start, end))
        if left_sorted[li][1] < right_sorted[ri][1]:
            li += 1
        else:
            ri += 1
    return result


def _subtract_intervals(
    windows: list[tuple[datetime, datetime]],
    blockers: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not windows:
        return []
    if not blockers:
        return _merge_intervals(windows)
    remaining = _merge_intervals(windows)
    for blocker_start, blocker_end in _merge_intervals(blockers):
        next_remaining: list[tuple[datetime, datetime]] = []
        for start, end in remaining:
            if blocker_end <= start or blocker_start >= end:
                next_remaining.append((start, end))
                continue
            if blocker_start > start:
                next_remaining.append((start, blocker_start))
            if blocker_end < end:
                next_remaining.append((blocker_end, end))
        remaining = next_remaining
        if not remaining:
            break
    return _merge_intervals(remaining)


def _split_interval_candidates(
    windows: list[tuple[datetime, datetime]],
    *,
    duration_minutes: int,
    step_minutes: int,
) -> list[datetime]:
    candidates: list[datetime] = []
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=max(step_minutes, 1))
    for start, end in windows:
        latest_start = end - duration
        cursor = start
        while cursor <= latest_start:
            candidates.append(cursor)
            cursor += step
    return candidates


def _default_windows_for_day(day: date) -> list[tuple[datetime, datetime]]:
    if day.weekday() > 4:
        return []
    windows = DEFAULT_OPEN_WINDOWS.get(day.weekday(), [])
    return [(_aware(day, start), _aware(day, end)) for start, end in windows]


def _rule_applies(rule: StaffAvailabilityRule, day: date) -> bool:
    if rule.weekday != day.weekday():
        return False
    if rule.effective_from and day < rule.effective_from:
        return False
    if rule.effective_to and day > rule.effective_to:
        return False
    return True


def _windows_for_user_day(
    *,
    day: date,
    rules: list[StaffAvailabilityRule],
    exceptions: list[StaffAvailabilityException],
    busy: list[tuple[datetime, datetime]],
    buffer_minutes: int,
) -> list[tuple[datetime, datetime]]:
    day_rules = [rule for rule in rules if _rule_applies(rule, day)]
    if day_rules:
        windows = [(_aware(day, rule.start_time), _aware(day, rule.end_time)) for rule in day_rules]
    else:
        windows = _default_windows_for_day(day)

    day_exceptions = [item for item in exceptions if item.date == day]
    if any(exc.type == AvailabilityExceptionType.CLOSED for exc in day_exceptions):
        return []

    custom_blockers = []
    for exc in day_exceptions:
        if exc.type == AvailabilityExceptionType.CUSTOM and exc.start_time and exc.end_time:
            custom_blockers.append((_aware(day, exc.start_time), _aware(day, exc.end_time)))

    expanded_busy: list[tuple[datetime, datetime]] = []
    buffer_delta = timedelta(minutes=max(buffer_minutes, 0))
    for start, end in busy:
        expanded_busy.append((start - buffer_delta, end + buffer_delta))

    available = _subtract_intervals(windows, custom_blockers)
    available = _subtract_intervals(available, expanded_busy)
    return available


def _policy_for_user(policy: StaffBookingPolicy | None) -> dict[str, Any]:
    if policy is None:
        return {
            "min_notice_minutes": 120,
            "max_days_ahead": 60,
            "buffer_minutes": 0,
            "allowed_durations": list(DEFAULT_ALLOWED_DURATIONS),
        }
    return {
        "min_notice_minutes": int(policy.min_notice_minutes or 120),
        "max_days_ahead": int(policy.max_days_ahead or 60),
        "buffer_minutes": int(policy.buffer_minutes or 0),
        "allowed_durations": policy.allowed_durations or list(DEFAULT_ALLOWED_DURATIONS),
    }


def _effective_policy(policies: list[StaffBookingPolicy | None]) -> dict[str, Any]:
    resolved = [_policy_for_user(policy) for policy in policies]
    if not resolved:
        return _policy_for_user(None)
    min_notice = max(item["min_notice_minutes"] for item in resolved)
    max_days = min(item["max_days_ahead"] for item in resolved)
    buffer_minutes = max(item["buffer_minutes"] for item in resolved)
    allowed_sets = [set(int(v) for v in item["allowed_durations"]) for item in resolved if item["allowed_durations"]]
    allowed = sorted(set.intersection(*allowed_sets)) if allowed_sets else list(DEFAULT_ALLOWED_DURATIONS)
    return {
        "min_notice_minutes": min_notice,
        "max_days_ahead": max_days,
        "buffer_minutes": buffer_minutes,
        "allowed_durations": allowed,
    }


def _load_rules(db: Session, user_ids: list[int]) -> dict[int, list[StaffAvailabilityRule]]:
    if not user_ids:
        return {}
    rows = db.scalars(
        select(StaffAvailabilityRule).where(StaffAvailabilityRule.user_id.in_(user_ids))
    ).all()
    grouped: dict[int, list[StaffAvailabilityRule]] = defaultdict(list)
    for row in rows:
        grouped[row.user_id].append(row)
    return grouped


def _load_exceptions(
    db: Session,
    user_ids: list[int],
    *,
    date_from: date,
    date_to: date,
) -> dict[int, list[StaffAvailabilityException]]:
    if not user_ids:
        return {}
    rows = db.scalars(
        select(StaffAvailabilityException).where(
            StaffAvailabilityException.user_id.in_(user_ids),
            StaffAvailabilityException.date >= date_from,
            StaffAvailabilityException.date <= date_to,
        )
    ).all()
    grouped: dict[int, list[StaffAvailabilityException]] = defaultdict(list)
    for row in rows:
        grouped[row.user_id].append(row)
    return grouped


def _load_policies(db: Session, user_ids: list[int]) -> dict[int, StaffBookingPolicy]:
    if not user_ids:
        return {}
    rows = db.scalars(
        select(StaffBookingPolicy).where(StaffBookingPolicy.user_id.in_(user_ids))
    ).all()
    return {row.user_id: row for row in rows}


def _load_connections(db: Session, user_ids: list[int]) -> dict[int, UserCalendarConnection]:
    if not user_ids:
        return {}
    rows = db.scalars(
        select(UserCalendarConnection).where(
            UserCalendarConnection.user_id.in_(user_ids),
            UserCalendarConnection.provider == CalendarProvider.GOOGLE.value,
        )
    ).all()
    return {row.user_id: row for row in rows}


def _to_google_time_range(date_from: date, date_to: date) -> tuple[str, str]:
    start = _aware(date_from, time(0, 0)).astimezone(timezone.utc)
    end = _aware(date_to + timedelta(days=1), time(0, 0)).astimezone(timezone.utc)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def _google_oauth_state(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "provider": CalendarProvider.GOOGLE.value,
        "nonce": secrets.token_urlsafe(16),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    raw = json.dumps(payload, separators=(",", ":"))
    return _encrypt(raw) or ""


def build_google_authorization_url(user: User, *, redirect_uri: str) -> str:
    params = {
        "client_id": settings.google_calendar_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_FREEBUSY_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": _google_oauth_state(user.id),
    }
    from urllib.parse import urlencode

    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_google_authorization_code(code: str, *, redirect_uri: str) -> dict[str, Any]:
    if not settings.google_calendar_client_id or not settings.google_calendar_client_secret:
        raise ValueError("Google Calendar OAuth client is not configured")
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_calendar_client_id,
            "client_secret": settings.google_calendar_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=20.0,
    )
    response.raise_for_status()
    return response.json()


def _refresh_google_access_token(connection: UserCalendarConnection) -> dict[str, Any] | None:
    refresh_token = _decrypt(connection.refresh_token_encrypted)
    if not refresh_token:
        return None
    if not settings.google_calendar_client_id or not settings.google_calendar_client_secret:
        return None
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_calendar_client_id,
            "client_secret": settings.google_calendar_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20.0,
    )
    response.raise_for_status()
    return response.json()


def _extract_google_busy(payload: dict[str, Any], *, calendar_id: str) -> list[tuple[datetime, datetime]]:
    calendars = payload.get("calendars") or {}
    calendar_payload = calendars.get(calendar_id) or {}
    busy_rows = calendar_payload.get("busy") or []
    intervals: list[tuple[datetime, datetime]] = []
    for row in busy_rows:
        start_raw = row.get("start")
        end_raw = row.get("end")
        if not start_raw or not end_raw:
            continue
        intervals.append((_localize(start_raw), _localize(end_raw)))
    return _merge_intervals(intervals)


def _google_freebusy_request(
    *,
    access_token: str,
    calendar_ids: list[str],
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    time_min, time_max = _to_google_time_range(date_from, date_to)
    response = httpx.post(
        GOOGLE_FREEBUSY_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": calendar_id} for calendar_id in calendar_ids],
        },
        timeout=20.0,
    )
    response.raise_for_status()
    return response.json()


def _google_cache_key(calendar_ids: list[str], date_from: date, date_to: date) -> str:
    raw = json.dumps({"ids": sorted(calendar_ids), "from": date_from.isoformat(), "to": date_to.isoformat()})
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _google_batch_freebusy(
    db: Session,
    connections: dict[int, UserCalendarConnection],
    user_ids: list[int],
    date_from: date,
    date_to: date,
) -> tuple[dict[int, list[tuple[datetime, datetime]]], dict[int, str], bool]:
    busy_by_user: dict[int, list[tuple[datetime, datetime]]] = {uid: [] for uid in user_ids}
    reasons: dict[int, str] = {}
    stale = False

    connected = [conn for conn in connections.values() if conn.freebusy_enabled and conn.revoked_at is None]
    if not connected:
        return busy_by_user, reasons, stale

    for batch_start in range(0, len(connected), 50):
        batch = connected[batch_start : batch_start + 50]
        calendar_ids = [conn.google_account_email for conn in batch if conn.google_account_email]
        if not calendar_ids:
            continue
        cache_key = _google_cache_key(calendar_ids, date_from, date_to)
        cached = _cache_get(cache_key)
        if cached is not None:
            for conn in batch:
                if conn.google_account_email:
                    busy_by_user.setdefault(conn.user_id, [])
                    busy_by_user[conn.user_id].extend(
                        (_localize(item["start"]), _localize(item["end"]))
                        for item in cached.get(conn.google_account_email, [])
                    )
            continue

        access_token = None
        last_failure: str | None = None
        for conn in batch:
            if not conn.google_account_email:
                continue
            if not conn.access_token_encrypted:
                continue
            token_expires_at = conn.token_expires_at
            if token_expires_at and token_expires_at <= now_ist():
                token_payload = _refresh_google_access_token(conn)
                if token_payload:
                    access_token = token_payload.get("access_token")
                    if access_token:
                        conn.access_token_encrypted = _encrypt(access_token)
                        expires_in = int(token_payload.get("expires_in") or 0)
                        conn.token_expires_at = now_ist() + timedelta(seconds=max(expires_in, 0)) if expires_in else None
                        if token_payload.get("refresh_token"):
                            conn.refresh_token_encrypted = _encrypt(token_payload.get("refresh_token"))
                        conn.last_sync_ok_at = now_ist()
                        conn.last_error = None
                        break
                last_failure = "Google access token expired and refresh failed"
            else:
                access_token = _decrypt(conn.access_token_encrypted)
                if access_token:
                    break
        if not access_token:
            if batch and last_failure:
                stale = True
                for conn in batch:
                    reasons[conn.user_id] = last_failure
            continue

        try:
            payload = _google_freebusy_request(
                access_token=access_token,
                calendar_ids=calendar_ids,
                date_from=date_from,
                date_to=date_to,
            )
            _cache_set(
                cache_key,
                {
                    calendar_id: [
                        {"start": item["start"], "end": item["end"]}
                        for item in (payload.get("calendars", {}).get(calendar_id, {}).get("busy") or [])
                    ]
                    for calendar_id in calendar_ids
                },
            )
            for conn in batch:
                if not conn.google_account_email:
                    continue
                intervals = _extract_google_busy(payload, calendar_id=conn.google_account_email)
                busy_by_user.setdefault(conn.user_id, [])
                busy_by_user[conn.user_id].extend(intervals)
                conn.last_sync_ok_at = now_ist()
                conn.last_error = None
        except Exception as exc:  # pragma: no cover - network failures are tested via monkeypatch
            stale = True
            last_failure = f"Google free/busy unavailable: {exc}"
            for conn in batch:
                if not conn.google_account_email:
                    continue
                reasons[conn.user_id] = last_failure
                conn.last_error = last_failure
            cached = _cache_get(cache_key)
            if cached is not None:
                for conn in batch:
                    if not conn.google_account_email:
                        continue
                    busy_by_user.setdefault(conn.user_id, [])
                    busy_by_user[conn.user_id].extend(
                        (_localize(item["start"]), _localize(item["end"]))
                        for item in cached.get(conn.google_account_email, [])
                    )

    for uid in busy_by_user:
        busy_by_user[uid] = _merge_intervals(busy_by_user[uid])
    return busy_by_user, reasons, stale


def busy_intervals(
    db: Session,
    user_ids: list[int],
    date_from: date,
    date_to: date,
    *,
    ignore_meeting_id: int | None = None,
) -> dict[int, list[tuple[datetime, datetime]]]:
    ids = _normalize_user_ids(user_ids)
    if not ids:
        return {}

    meetings = db.scalars(
        select(CaseManagerMeeting).where(
            CaseManagerMeeting.scheduled_date >= date_from,
            CaseManagerMeeting.scheduled_date <= date_to,
            CaseManagerMeeting.status.in_(
                [MeetingStatus.SCHEDULED, MeetingStatus.COMPLETED, MeetingStatus.NO_SHOW]
            ),
        )
    ).all()
    sessions = db.scalars(
        select(TherapySession).where(
            TherapySession.scheduled_date >= date_from,
            TherapySession.scheduled_date <= date_to,
            TherapySession.status.in_(
                [SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS, SessionStatus.COMPLETED]
            ),
        )
    ).all()

    busy: dict[int, list[tuple[datetime, datetime]]] = {uid: [] for uid in ids}
    id_set = set(ids)

    for meeting in meetings:
        if ignore_meeting_id is not None and meeting.id == ignore_meeting_id:
            continue
        if not meeting.scheduled_time:
            continue
        participants = meeting_participant_user_ids(meeting)
        impacted = participants.intersection(id_set)
        if not impacted:
            continue
        start = _aware(meeting.scheduled_date, meeting.scheduled_time)
        end = start + timedelta(minutes=int(meeting.duration_minutes or 30))
        for uid in impacted:
            busy.setdefault(uid, []).append((start, end))

    for session in sessions:
        if session.therapist_user_id not in id_set or not session.start_time:
            continue
        start = _aware(session.scheduled_date, session.start_time)
        duration = int(session.scheduled_duration_mins or 60)
        end = start + timedelta(minutes=duration)
        busy.setdefault(session.therapist_user_id, []).append((start, end))

    return {uid: _merge_intervals(rows) for uid, rows in busy.items() if rows}


def external_busy_intervals(
    db: Session,
    user_ids: list[int],
    date_from: date,
    date_to: date,
) -> dict[int, list[tuple[datetime, datetime]]]:
    ids = _normalize_user_ids(user_ids)
    if not ids:
        return {}
    if not settings.google_calendar_freebusy_enabled:
        return {}

    connections = _load_connections(db, ids)
    busy_by_user, _reasons, _stale = _google_batch_freebusy(
        db,
        connections,
        ids,
        date_from,
        date_to,
    )
    return {uid: rows for uid, rows in busy_by_user.items() if rows}


def free_slots(
    db: Session,
    user_ids: list[int],
    date_from: date,
    date_to: date,
    duration_minutes: int,
    requesting_user: User | None,
) -> dict[str, Any]:
    _ = requesting_user
    ids = _normalize_user_ids(user_ids)
    if date_to < date_from:
        raise ValueError("date_to must be on or after date_from")
    if not ids:
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "duration_minutes": duration_minutes,
            "user_ids": [],
            "slots": [],
            "alternate_suggestions": [],
            "freebusy_stale": False,
            "freebusy_reasons": {},
        }

    rules_by_user = _load_rules(db, ids)
    exceptions_by_user = _load_exceptions(db, ids, date_from=date_from, date_to=date_to)
    policies_by_user = _load_policies(db, ids)
    connections_by_user = _load_connections(db, ids)

    effective_policy = _effective_policy([policies_by_user.get(uid) for uid in ids])
    allowed_durations = set(int(v) for v in effective_policy["allowed_durations"])
    duration = int(duration_minutes)
    freebusy_stale = False
    freebusy_reasons: dict[int, str] = {}

    if duration not in allowed_durations:
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "duration_minutes": duration,
            "user_ids": ids,
            "slots": [],
            "alternate_suggestions": [],
            "freebusy_stale": False,
            "freebusy_reasons": {
                uid: f"Duration {duration} is not allowed by booking policy"
                for uid in ids
            },
            "policy": effective_policy,
        }

    local_busy = busy_intervals(db, ids, date_from, date_to)
    google_busy: dict[int, list] = {uid: [] for uid in ids}
    google_reasons: dict[int, str] = {}
    google_stale = False
    if settings.google_calendar_freebusy_enabled:
        google_busy, google_reasons, google_stale = _google_batch_freebusy(
            db,
            connections_by_user,
            ids,
            date_from,
            date_to,
        )
    freebusy_stale = google_stale
    freebusy_reasons.update(google_reasons)

    now = now_ist()
    min_notice = timedelta(minutes=int(effective_policy["min_notice_minutes"]))
    max_days_ahead = int(effective_policy["max_days_ahead"])
    buffer_minutes = int(effective_policy["buffer_minutes"])
    slots: list[dict[str, Any]] = []
    alternate_suggestions: list[dict[str, Any]] = []

    def _slots_for_day(day: date) -> list[dict[str, Any]]:
        per_user_windows: list[list[tuple[datetime, datetime]]] = []
        step_sizes: list[int] = []
        for uid in ids:
            rules = rules_by_user.get(uid, [])
            exceptions = exceptions_by_user.get(uid, [])
            busy = list(local_busy.get(uid, [])) + list(google_busy.get(uid, []))
            windows = _windows_for_user_day(
                day=day,
                rules=rules,
                exceptions=exceptions,
                busy=busy,
                buffer_minutes=buffer_minutes,
            )
            if not windows:
                per_user_windows = []
                break
            per_user_windows.append(windows)
            applicable_rules = [rule for rule in rules if _rule_applies(rule, day)]
            if applicable_rules:
                step_sizes.append(min(max(rule.slot_granularity_minutes or 30, 1) for rule in applicable_rules))
            else:
                step_sizes.append(30)

        if not per_user_windows:
            return []

        shared = per_user_windows[0]
        for other in per_user_windows[1:]:
            shared = _intersect_intervals(shared, other)
            if not shared:
                break
        if not shared:
            return []

        step = max(1, min(step_sizes) if step_sizes else 30)
        candidates = _split_interval_candidates(shared, duration_minutes=duration, step_minutes=step)
        day_slots: list[dict[str, Any]] = []
        for start in candidates:
            if start < now + min_notice:
                continue
            if (start.date() - now.date()).days > max_days_ahead:
                continue
            day_slots.append(
                {
                    "date": start.date().isoformat(),
                    "time": start.strftime("%H:%M"),
                    "available": True,
                    "reason": None,
                }
            )
        return day_slots

    for day_offset in range((date_to - date_from).days + 1):
        day = date_from + timedelta(days=day_offset)
        slots.extend(_slots_for_day(day))

    if not slots:
        for day_offset in range(1, 8):
            alt_day = date_from + timedelta(days=day_offset)
            if alt_day > date_to + timedelta(days=7):
                break
            if alt_day < date_from:
                continue
            alt_slots = [item["time"] for item in _slots_for_day(alt_day)[:3]]
            if alt_slots:
                alternate_suggestions.append({"date": alt_day.isoformat(), "slots": alt_slots})
            if len(alternate_suggestions) >= 3:
                break

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "duration_minutes": duration,
        "user_ids": ids,
        "slots": slots,
        "alternate_suggestions": alternate_suggestions,
        "freebusy_stale": freebusy_stale,
        "freebusy_reasons": freebusy_reasons,
        "policy": effective_policy,
    }


def load_user_availability(db: Session, user_id: int) -> dict[str, Any]:
    rules = db.scalars(
        select(StaffAvailabilityRule).where(StaffAvailabilityRule.user_id == user_id).order_by(
            StaffAvailabilityRule.weekday,
            StaffAvailabilityRule.start_time,
        )
    ).all()
    exceptions = db.scalars(
        select(StaffAvailabilityException).where(StaffAvailabilityException.user_id == user_id).order_by(
            StaffAvailabilityException.date.desc()
        )
    ).all()
    policy = db.scalars(
        select(StaffBookingPolicy).where(StaffBookingPolicy.user_id == user_id)
    ).first()
    connection = db.scalars(
        select(UserCalendarConnection).where(
            UserCalendarConnection.user_id == user_id,
            UserCalendarConnection.provider == CalendarProvider.GOOGLE.value,
        )
    ).first()

    rule_rows = [
        {
            "id": rule.id,
            "weekday": rule.weekday,
            "start_time": rule.start_time.strftime("%H:%M"),
            "end_time": rule.end_time.strftime("%H:%M"),
            "effective_from": rule.effective_from.isoformat() if rule.effective_from else None,
            "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
            "slot_granularity_minutes": rule.slot_granularity_minutes or 30,
        }
        for rule in rules
    ]
    if not rule_rows:
        rule_rows = [
            {
                "weekday": weekday,
                "start_time": "10:00",
                "end_time": "19:00",
                "effective_from": None,
                "effective_to": None,
                "slot_granularity_minutes": 30,
                "is_default": True,
            }
            for weekday in range(5)
        ]

    return {
        "user_id": user_id,
        "rules": rule_rows,
        "exceptions": [
            {
                "id": exc.id,
                "date": exc.date.isoformat(),
                "type": exc.type.value,
                "start_time": exc.start_time.strftime("%H:%M") if exc.start_time else None,
                "end_time": exc.end_time.strftime("%H:%M") if exc.end_time else None,
                "reason": exc.reason,
            }
            for exc in exceptions
        ],
        "booking_policy": _policy_for_user(policy),
        "google_connection": {
            "provider": CalendarProvider.GOOGLE.value,
            "google_account_email": connection.google_account_email if connection else None,
            "freebusy_enabled": connection.freebusy_enabled if connection else False,
            "last_sync_ok_at": connection.last_sync_ok_at.isoformat() if connection and connection.last_sync_ok_at else None,
            "last_error": connection.last_error if connection else None,
            "connected_at": connection.connected_at.isoformat() if connection and connection.connected_at else None,
            "revoked_at": connection.revoked_at.isoformat() if connection and connection.revoked_at else None,
            "is_connected": bool(connection and connection.is_connected),
        },
    }


def save_user_availability(db: Session, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    rules = payload.get("rules") or []
    exceptions = payload.get("exceptions") or []
    booking_policy = payload.get("booking_policy") or {}

    db.query(StaffAvailabilityRule).filter(StaffAvailabilityRule.user_id == user_id).delete(synchronize_session=False)
    db.query(StaffAvailabilityException).filter(
        StaffAvailabilityException.user_id == user_id
    ).delete(synchronize_session=False)

    for row in rules:
        start = row.get("start_time")
        end = row.get("end_time")
        if start and end:
            db.add(
                StaffAvailabilityRule(
                    user_id=user_id,
                    weekday=int(row.get("weekday", 0)),
                    start_time=time.fromisoformat(str(start)),
                    end_time=time.fromisoformat(str(end)),
                    effective_from=_coerce_date(row.get("effective_from")),
                    effective_to=_coerce_date(row.get("effective_to")),
                    slot_granularity_minutes=int(row.get("slot_granularity_minutes") or 30),
                )
            )

    for row in exceptions:
        db.add(
            StaffAvailabilityException(
                user_id=user_id,
                date=_coerce_date(row.get("date")) or date.today(),
                type=AvailabilityExceptionType(row.get("type") or AvailabilityExceptionType.CLOSED.value),
                start_time=time.fromisoformat(str(row["start_time"])) if row.get("start_time") else None,
                end_time=time.fromisoformat(str(row["end_time"])) if row.get("end_time") else None,
                reason=(row.get("reason") or "").strip() or None,
            )
        )

    policy = db.scalars(
        select(StaffBookingPolicy).where(StaffBookingPolicy.user_id == user_id)
    ).first()
    if policy is None:
        policy = StaffBookingPolicy(user_id=user_id)
        db.add(policy)
    policy.min_notice_minutes = int(booking_policy.get("min_notice_minutes") or 120)
    policy.max_days_ahead = int(booking_policy.get("max_days_ahead") or 60)
    policy.buffer_minutes = int(booking_policy.get("buffer_minutes") or 0)
    durations = booking_policy.get("allowed_durations") or DEFAULT_ALLOWED_DURATIONS
    if isinstance(durations, str):
        durations = [item.strip() for item in durations.split(",") if item.strip()]
    policy.allowed_durations_json = [int(value) for value in durations]

    db.flush()
    return load_user_availability(db, user_id)


def _state_user_id(state: str | None) -> int | None:
    if not state:
        return None
    raw = _decrypt(state)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if payload.get("provider") != CalendarProvider.GOOGLE.value:
        return None
    return int(payload.get("user_id") or 0) or None


def upsert_google_connection_from_callback(
    db: Session,
    *,
    state: str,
    code: str,
    redirect_uri: str,
) -> UserCalendarConnection:
    user_id = _state_user_id(state)
    if not user_id:
        raise ValueError("Invalid Google calendar state")
    token_data = exchange_google_authorization_code(code, redirect_uri=redirect_uri)
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = int(token_data.get("expires_in") or 0)
    google_email = token_data.get("email") or token_data.get("google_account_email")
    if not access_token:
        raise ValueError("Google did not return an access token")

    connection = db.scalars(
        select(UserCalendarConnection).where(
            UserCalendarConnection.user_id == user_id,
            UserCalendarConnection.provider == CalendarProvider.GOOGLE.value,
        )
    ).first()
    if connection is None:
        connection = UserCalendarConnection(user_id=user_id, provider=CalendarProvider.GOOGLE.value)
        db.add(connection)
    connection.google_account_email = google_email
    connection.access_token_encrypted = _encrypt(access_token)
    if refresh_token:
        connection.refresh_token_encrypted = _encrypt(refresh_token)
    connection.token_expires_at = now_ist() + timedelta(seconds=max(expires_in, 0)) if expires_in else None
    connection.freebusy_enabled = True
    connection.last_sync_ok_at = now_ist()
    connection.last_error = None
    connection.connected_at = now_ist()
    connection.revoked_at = None
    db.flush()
    return connection


def revoke_google_connection(db: Session, user_id: int) -> UserCalendarConnection | None:
    connection = db.scalars(
        select(UserCalendarConnection).where(
            UserCalendarConnection.user_id == user_id,
            UserCalendarConnection.provider == CalendarProvider.GOOGLE.value,
        )
    ).first()
    if connection is None:
        return None
    connection.revoked_at = now_ist()
    connection.freebusy_enabled = False
    connection.access_token_encrypted = None
    connection.refresh_token_encrypted = None
    connection.last_error = "Disconnected by user"
    db.flush()
    return connection


def serialize_google_connection(connection: UserCalendarConnection | None) -> dict[str, Any] | None:
    if connection is None:
        return None
    return {
        "provider": connection.provider,
        "google_account_email": connection.google_account_email,
        "freebusy_enabled": connection.freebusy_enabled,
        "last_sync_ok_at": connection.last_sync_ok_at.isoformat() if connection.last_sync_ok_at else None,
        "last_error": connection.last_error,
        "connected_at": connection.connected_at.isoformat() if connection.connected_at else None,
        "revoked_at": connection.revoked_at.isoformat() if connection.revoked_at else None,
        "is_connected": connection.is_connected,
    }

