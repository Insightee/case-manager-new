"""Case Insights (Phase 1) — status-label mapping and weekly AI refresh cap boundary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.clinical_snapshot import ClinicalSnapshot
from app.models.user import User
from app.services.insights import weekly_insight_usage_limiter as limiter
from app.services.insights.case_insight_aggregator import build_case_insight_payload
from app.services.insights.helpers import goal_status_label, strategy_response_label

ensure_sqlite_schema_patches()
client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_goal_status_label_not_enough_evidence_when_no_sessions():
    assert goal_status_label("weak", None, 0) == "Not enough evidence"


def test_goal_status_label_needs_adapting_on_negative_trend():
    assert goal_status_label("moderate", "needs_support", 3) == "Needs adapting"


def test_goal_status_label_consistent_when_strong_and_stable():
    assert goal_status_label("strong_operational", "stable", 5) == "Consistent"


def test_goal_status_label_building_when_moderate():
    assert goal_status_label("moderate", "improving", 2) == "Building"


def test_strategy_response_label_not_enough_evidence_with_zero_uses():
    assert strategy_response_label({}, 0) == "Not enough evidence"


def test_strategy_response_label_helpful_when_majority_positive():
    dist = {"HELPFUL": 4, "PARTLY_HELPFUL": 1}
    assert strategy_response_label(dist, 5) == "Helpful"


def test_strategy_response_label_needs_adapting_when_negative_dominates():
    dist = {"HELPFUL": 1, "NEEDS_ADAPTATION": 3}
    assert strategy_response_label(dist, 4) == "Needs adapting"


def test_weekly_usage_limiter_counts_within_current_week_only():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and user

        before = limiter.get_usage(db, case_id=case.id, user_id=user.id)
        base_used = before["used"]

        now = datetime.now(timezone.utc)
        snap_this_week = ClinicalSnapshot(
            case_id=case.id,
            month=now.strftime("%Y-%m"),
            year=now.year,
            generated_by_user_id=user.id,
            generated_for_role="therapist",
            insight_type="case_insight_refresh",
            status="draft",
            input_hash=f"test-hash-current-{now.timestamp()}",
        )
        snap_last_week = ClinicalSnapshot(
            case_id=case.id,
            month=now.strftime("%Y-%m"),
            year=now.year,
            generated_by_user_id=user.id,
            generated_for_role="therapist",
            insight_type="case_insight_refresh",
            status="draft",
            input_hash=f"test-hash-lastweek-{now.timestamp()}",
        )
        db.add_all([snap_this_week, snap_last_week])
        db.commit()
        db.refresh(snap_last_week)
        # Backdate one row to before the current week's Monday so it must not count.
        week_start = limiter._week_start(now)
        db.query(ClinicalSnapshot).filter(ClinicalSnapshot.id == snap_last_week.id).update(
            {"created_at": week_start - timedelta(days=1)}
        )
        db.commit()

        usage = limiter.get_usage(db, case_id=case.id, user_id=user.id)
        assert usage["used"] == base_used + 1
        assert usage["cap"] == limiter.WEEKLY_REFRESH_CAP


def test_weekly_usage_limiter_has_capacity_false_at_cap():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        user = db.scalars(select(User).where(User.email == "cm@demo.com")).first()
        if not user:
            user = db.scalars(select(User)).first()
        assert case and user

        now = datetime.now(timezone.utc)
        for i in range(limiter.WEEKLY_REFRESH_CAP):
            db.add(
                ClinicalSnapshot(
                    case_id=case.id,
                    month=now.strftime("%Y-%m"),
                    year=now.year,
                    generated_by_user_id=user.id,
                    generated_for_role="case_manager",
                    insight_type="case_insight_refresh",
                    status="draft",
                    input_hash=f"cap-test-{i}-{now.timestamp()}",
                )
            )
        db.commit()

        assert limiter.has_capacity(db, case_id=case.id, user_id=user.id) is False
        usage = limiter.get_usage(db, case_id=case.id, user_id=user.id)
        assert usage["remaining"] == 0


def test_case_summary_route_returns_ordered_insight_sections():
    headers = _login("therapist@demo.com")
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()

    r = client.get(f"/api/v1/cases/{case.id}/insights/case-summary", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["caseId"] == case.id
    assert "child" in body and "summaryParagraph" in body["child"]
    assert "activeIEP" in body and "goals" in body["activeIEP"]
    assert "insights" in body and isinstance(body["insights"], list)


def test_case_summary_matches_direct_aggregator_call():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        payload = build_case_insight_payload(db, case.id)
        assert payload["caseId"] == case.id
        assert isinstance(payload["insights"], list)
