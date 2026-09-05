from __future__ import annotations

from datetime import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.scheduling_defaults import KEY_TO_WEEKDAY, WEEKDAY_TO_KEY, default_schedule_days
from app.models.calendar_availability import StaffAvailabilityRule, StaffBookingPolicy
from app.models.schedule_template import TherapistScheduleTemplate, default_template_config
from app.services.slot_calendar_service import normalize_day_config


def _hm(value: time | str) -> str:
    if isinstance(value, time):
        return value.strftime("%H:%M")
    text = str(value).strip()
    return text[:5] if len(text) >= 5 else text


def rules_to_template_days(rules: list[StaffAvailabilityRule]) -> dict[str, dict[str, Any]]:
    days = default_schedule_days()
    for key in days:
        days[key] = {**days[key], "enabled": False, "windows": []}

    grouped: dict[int, list[StaffAvailabilityRule]] = {}
    for rule in rules:
        grouped.setdefault(rule.weekday, []).append(rule)

    for weekday, day_rules in grouped.items():
        key = WEEKDAY_TO_KEY.get(weekday)
        if not key:
            continue
        windows = [
            {"start": _hm(rule.start_time), "end": _hm(rule.end_time)}
            for rule in sorted(day_rules, key=lambda row: row.start_time)
        ]
        if not windows:
            continue
        days[key] = {
            "enabled": True,
            "start": windows[0]["start"],
            "end": windows[0]["end"],
            "windows": windows,
        }
    return days


def template_days_to_rules(days_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for key, raw_day in (days_cfg or {}).items():
        weekday = KEY_TO_WEEKDAY.get(key)
        if weekday is None:
            continue
        day = normalize_day_config(raw_day)
        if not day.get("enabled"):
            continue
        for window in day.get("windows") or []:
            start = window.get("start")
            end = window.get("end")
            if not start or not end:
                continue
            rules.append(
                {
                    "weekday": weekday,
                    "start_time": _hm(start),
                    "end_time": _hm(end),
                    "slot_granularity_minutes": 30,
                }
            )
    return rules


def sync_staff_rules_to_template(db: Session, user_id: int) -> TherapistScheduleTemplate | None:
    rules = list(
        db.scalars(
            select(StaffAvailabilityRule)
            .where(StaffAvailabilityRule.user_id == user_id)
            .order_by(StaffAvailabilityRule.weekday, StaffAvailabilityRule.start_time)
        ).all()
    )
    if not rules:
        return None

    from app.services.slot_calendar_service import get_or_create_template

    row = get_or_create_template(db, user_id)
    config = row.get_config()
    config["days"] = rules_to_template_days(rules)
    row.set_config(config)
    db.flush()
    return row


def sync_template_to_staff_rules(db: Session, user_id: int, config: dict[str, Any]) -> bool:
    rules_payload = template_days_to_rules(config.get("days") or {})
    if not rules_payload:
        return False

    policy = db.scalars(select(StaffBookingPolicy).where(StaffBookingPolicy.user_id == user_id)).first()
    if policy is None:
        policy = StaffBookingPolicy(user_id=user_id)
        db.add(policy)
        policy.min_notice_minutes = 120
        policy.max_days_ahead = 60
        policy.buffer_minutes = 0
        policy.allowed_durations_json = [30, 45, 60, 90]

    db.query(StaffAvailabilityRule).filter(StaffAvailabilityRule.user_id == user_id).delete(
        synchronize_session=False
    )
    for row in rules_payload:
        db.add(
            StaffAvailabilityRule(
                user_id=user_id,
                weekday=int(row["weekday"]),
                start_time=time.fromisoformat(str(row["start_time"])),
                end_time=time.fromisoformat(str(row["end_time"])),
                slot_granularity_minutes=int(row.get("slot_granularity_minutes") or 30),
            )
        )
    db.flush()
    return True


def merge_template_config(existing: dict[str, Any] | None) -> dict[str, Any]:
    base = default_template_config()
    if not existing:
        return base
    merged = {**base, **existing}
    merged["days"] = {**base["days"], **(existing.get("days") or {})}
    for key, day in merged["days"].items():
        if key in (existing.get("days") or {}):
            merged["days"][key] = {**base["days"].get(key, {}), **existing["days"][key]}
    return merged
