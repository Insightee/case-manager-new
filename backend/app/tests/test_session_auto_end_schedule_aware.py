"""Schedule-aware auto-close caps across service categories."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.core.clinical_service_resolver import normalize_clinical_token, resolve_clinical_service_category
from app.core.session_rules import (
    CATEGORY_AFTER_SCHEDULE_BUFFER_MINUTES,
    compute_auto_end_cap,
    scheduled_end_at_utc,
)
from app.core.timezone import ensure_utc_aware
from app.services import session_day_end_service

IST = ZoneInfo("Asia/Kolkata")
SCHEDULED_DAY = date(2026, 6, 24)


def _ist_utc(d: date, hour: int, minute: int) -> datetime:
    return datetime.combine(d, time(hour, minute), tzinfo=IST).astimezone(timezone.utc)


def _case(product_module: str, service_type: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        product_module=product_module,
        service_type=service_type,
        services=[],
    )


def _assert_cap_at_or_after_scheduled_end(
    *,
    started_at: datetime,
    end_time: time,
    product_module: str,
    service_category: str | None = None,
) -> datetime:
    cap, _reason, _sched_mins, _overage = compute_auto_end_cap(
        started_at=started_at,
        scheduled_date=SCHEDULED_DAY,
        start_time=time(7, 48),
        end_time=end_time,
        product_module=product_module,
        service_category=service_category,
    )
    sched_end = scheduled_end_at_utc(SCHEDULED_DAY, end_time)
    assert sched_end is not None
    assert cap >= sched_end, f"cap {cap} before scheduled end {sched_end}"
    return cap


def test_scheduled_long_shadow_session_not_capped_at_four_hours():
    started = _ist_utc(SCHEDULED_DAY, 7, 48)
    cap = _assert_cap_at_or_after_scheduled_end(
        started_at=started,
        end_time=time(15, 15),
        product_module="shadow_support",
        service_category="shadow_support",
    )
    buffer_mins = CATEGORY_AFTER_SCHEDULE_BUFFER_MINUTES["shadow_support"]
    expected_min = scheduled_end_at_utc(SCHEDULED_DAY, time(15, 15)) + timedelta(minutes=buffer_mins)
    assert cap == expected_min
    assert cap > started + timedelta(hours=4)


def test_scheduled_unknown_clinical_not_capped_at_four_hours():
    started = _ist_utc(SCHEDULED_DAY, 7, 48)
    cap = _assert_cap_at_or_after_scheduled_end(
        started_at=started,
        end_time=time(15, 15),
        product_module="occupational_therapy",
        service_category="other_clinical",
    )
    assert cap > started + timedelta(hours=4)


def test_unknown_unscheduled_session_uses_four_hour_fallback():
    started = _ist_utc(SCHEDULED_DAY, 7, 48)
    cap, reason, _, _ = compute_auto_end_cap(
        started_at=started,
        scheduled_date=SCHEDULED_DAY,
        start_time=time(7, 48),
        end_time=None,
        product_module="unknown_clinical_line",
        service_category="unknown",
    )
    assert cap == started + timedelta(hours=4)
    assert reason == "slot_duration_limit"


def test_homecare_short_scheduled_session_cap_after_end_plus_buffer():
    started = _ist_utc(SCHEDULED_DAY, 9, 0)
    cap, reason, _, _ = compute_auto_end_cap(
        started_at=started,
        scheduled_date=SCHEDULED_DAY,
        start_time=time(9, 0),
        end_time=time(10, 0),
        product_module="homecare",
        service_category="homecare",
    )
    sched_end = scheduled_end_at_utc(SCHEDULED_DAY, time(10, 0))
    assert cap == sched_end + timedelta(minutes=CATEGORY_AFTER_SCHEDULE_BUFFER_MINUTES["homecare"])
    assert reason == "homecare_duration_limit"


def test_homecare_long_scheduled_session_not_before_scheduled_end():
    started = _ist_utc(SCHEDULED_DAY, 9, 0)
    _assert_cap_at_or_after_scheduled_end(
        started_at=started,
        end_time=time(13, 0),
        product_module="homecare",
        service_category="homecare",
    )


@pytest.mark.parametrize(
    ("category", "product_module", "end_h", "end_m"),
    [
        ("special_education", "special_educator", 12, 30),
        ("behavior_therapy", "behavior_therapy", 12, 0),
        ("play_therapy", "play_therapy", 12, 0),
        ("counselling", "counselling", 11, 0),
    ],
)
def test_scheduled_clinical_categories_respect_scheduled_end(category, product_module, end_h, end_m):
    started = _ist_utc(SCHEDULED_DAY, 10, 0)
    _assert_cap_at_or_after_scheduled_end(
        started_at=started,
        end_time=time(end_h, end_m),
        product_module=product_module,
        service_category=category,
    )


def test_reproduction_case_unknown_module_scheduled_0748_1515():
    """Regression: 07:48–15:15 must not auto-close at 11:48 (4h fallback)."""
    started = _ist_utc(SCHEDULED_DAY, 7, 48)
    cap, reason, _, _ = compute_auto_end_cap(
        started_at=started,
        scheduled_date=SCHEDULED_DAY,
        start_time=time(7, 48),
        end_time=time(15, 15),
        product_module="billing",
        service_category="unknown",
    )
    wrong_cap = started + timedelta(hours=4)
    assert cap > wrong_cap
    assert cap >= scheduled_end_at_utc(SCHEDULED_DAY, time(15, 15))
    assert reason == "scheduled_window_cap"


def test_min_caps_cannot_select_before_scheduled_end():
    started = _ist_utc(SCHEDULED_DAY, 7, 48)
    sched_end = scheduled_end_at_utc(SCHEDULED_DAY, time(15, 15))
    early_fallback = started + timedelta(hours=4)
    assert early_fallback < sched_end
    cap, _, _, _ = compute_auto_end_cap(
        started_at=started,
        scheduled_date=SCHEDULED_DAY,
        start_time=time(7, 48),
        end_time=time(15, 15),
        product_module="non_homecare_non_shadow",
        service_category="unknown",
    )
    assert cap >= sched_end


def test_day_end_10pm_ist_unchanged(monkeypatch):
    from app.core.database import SessionLocal
    from app.models.case import Case
    from app.models.session import Session as TherapySession
    from app.models.session import SessionMode, SessionStatus
    from app.models.user import User
    from sqlalchemy import select

    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        if not therapist or not case:
            pytest.skip("Seed data missing")
        today = SCHEDULED_DAY
        started = _ist_utc(today, 14, 0)
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=today,
            start_time=time(7, 48),
            end_time=time(15, 15),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=started,
        )
        db.add(session)
        db.commit()
        sid = session.id
        now_ist = datetime.combine(today, time(22, 30), tzinfo=IST)
        closed = session_day_end_service.auto_close_open_sessions_at_day_end(db, now_ist)
        db.commit()
        assert sid in closed
        refreshed = db.get(TherapySession, sid)
        assert refreshed.auto_end_reason == "day_end_10pm_ist"
        end_ist = ensure_utc_aware(refreshed.actual_end_at).astimezone(IST)
        assert end_ist.hour == 22
    finally:
        db.rollback()
        db.close()


def test_resolver_aliases():
    assert normalize_clinical_token("Shadow Support") == "shadow_support"
    assert normalize_clinical_token("home care") == "homecare"
    assert normalize_clinical_token("special educator") == "special_education"
    assert normalize_clinical_token("behaviour therapy") == "behavior_therapy"
    assert normalize_clinical_token("counseling") == "counselling"
    case = _case("billing", service_type="School Shadow")
    assert resolve_clinical_service_category(case) in ("shadow_support", "school_support", "other_clinical")
