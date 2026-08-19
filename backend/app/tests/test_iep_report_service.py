"""IEP report service — start, goals, submit, approve, parent preview."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.clinical_evidence import IepGoalCard
from app.models.clinical_report import ClinicalReportStatus

client = TestClient(app)
ensure_sqlite_schema_patches()

GOAL_PAYLOAD = {
    "title": "Social initiation with peers",
    "goal_statement": "Will initiate peer play during unstructured periods.",
    "domain": "communication",
    "baseline_current_state": "Observes peers; rarely initiates.",
    "desired_state": "Initiates play 4/5 opportunities.",
    "participation": "emerging_participation",
    "independence_support_needed": "moderate_support",
    "goal_achievement": "emerging",
}


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _case_id() -> int:
    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        return case.id


def _start_iep(headers: dict) -> int:
    case_id = _case_id()
    r = client.post(f"/api/v1/cases/{case_id}/reports/iep/start", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["report_id"]


def _seed_iep_sections(report_id: int, headers: dict) -> None:
    client.patch(
        f"/api/v1/reports/{report_id}/sections/child_context",
        headers=headers,
        json={"narrative_text": "Strengths-forward child context from observation."},
    )
    client.patch(
        f"/api/v1/reports/{report_id}/sections/priority_domains",
        headers=headers,
        json={"structured_data": {"domains": ["communication", "participation"]}},
    )


def test_iep_summary_and_start():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = _case_id()

    r = client.get(f"/api/v1/cases/{case_id}/reports/iep/summary", headers=headers)
    assert r.status_code == 200
    assert "has_report" in r.json()

    report_id = _start_iep(headers)
    assert report_id

    r = client.get(f"/api/v1/cases/{case_id}/reports/iep", headers=headers)
    assert r.status_code == 200
    assert r.json()["report_type"] == "iep"


def test_iep_start_unexpected_error_is_json_503(monkeypatch):
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = _case_id()

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated start failure")

    monkeypatch.setattr("app.services.iep_report_service.start_iep", boom)
    r = client.post(f"/api/v1/cases/{case_id}/reports/iep/start", headers=headers)
    assert r.status_code == 503
    assert r.json()["detail"] == "Could not start IEP"


def test_parent_cannot_start_iep():
    token = _login("parent@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = _case_id()
    r = client.post(f"/api/v1/cases/{case_id}/reports/iep/start", headers=headers)
    assert r.status_code in (403, 404)


def test_iep_generate_draft_manual_without_observation_warning():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    report_id = _start_iep(headers)
    r = client.post(f"/api/v1/reports/{report_id}/iep/generate-draft", headers=headers)
    assert r.status_code == 200, r.text
    draft = r.json()["draft"]
    assert "warning" in draft or "goals_imported" in draft


def test_iep_add_goal_patch_and_submit_validation():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    report_id = _start_iep(headers)
    _seed_iep_sections(report_id, headers)

    r = client.post(f"/api/v1/reports/{report_id}/iep/goals", headers=headers, json=GOAL_PAYLOAD)
    assert r.status_code == 200, r.text
    iep_goal_id = r.json()["iep_goal_id"]

    r = client.patch(
        f"/api/v1/reports/{report_id}/iep/goals/{iep_goal_id}",
        headers=headers,
        json={"participation": "participates_with_support"},
    )
    assert r.status_code == 200

    r = client.post(f"/api/v1/reports/{report_id}/submit", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value


def test_iep_parent_preview_hides_internal():
    therapist = _login("therapist@demo.com")
    admin = _login("superadmin@demo.com")
    th = {"Authorization": f"Bearer {therapist}"}
    ah = {"Authorization": f"Bearer {admin}"}
    report_id = _start_iep(th)
    _seed_iep_sections(report_id, th)
    client.post(f"/api/v1/reports/{report_id}/iep/goals", headers=th, json=GOAL_PAYLOAD)
    client.patch(
        f"/api/v1/reports/{report_id}/sections/internal_cm_notes",
        headers=th,
        json={"narrative_text": "Secret CM note"},
    )
    client.post(f"/api/v1/reports/{report_id}/submit", headers=th)
    client.post(f"/api/v1/reports/{report_id}/approve", headers=ah, json={"share_with_parent": False})

    r = client.get(f"/api/v1/reports/{report_id}/iep/preview?mode=parent", headers=th)
    assert r.status_code == 200
    keys = [s["key"] for s in r.json()["sections"]]
    assert "internal_cm_notes" not in keys


def test_iep_approve_sync_idempotent():
    therapist = _login("therapist@demo.com")
    admin = _login("superadmin@demo.com")
    th = {"Authorization": f"Bearer {therapist}"}
    ah = {"Authorization": f"Bearer {admin}"}
    report_id = _start_iep(th)
    _seed_iep_sections(report_id, th)
    client.post(f"/api/v1/reports/{report_id}/iep/goals", headers=th, json=GOAL_PAYLOAD)
    client.post(f"/api/v1/reports/{report_id}/submit", headers=th)
    client.post(f"/api/v1/reports/{report_id}/approve", headers=ah, json={})

    r = client.post(f"/api/v1/reports/{report_id}/iep/sync-active-plan", headers=ah)
    assert r.status_code == 200
    first = r.json()["synced"]

    r = client.post(f"/api/v1/reports/{report_id}/iep/sync-active-plan", headers=ah)
    assert r.status_code == 200
    second = r.json()["synced"]
    assert second >= first

    with SessionLocal() as db:
        case_id = _case_id()
        count = len(list(db.scalars(select(IepGoalCard).where(IepGoalCard.case_id == case_id)).all()))
        assert count >= 1


def test_iep_mark_achieved():
    therapist = _login("therapist@demo.com")
    admin = _login("superadmin@demo.com")
    th = {"Authorization": f"Bearer {therapist}"}
    ah = {"Authorization": f"Bearer {admin}"}
    report_id = _start_iep(th)
    _seed_iep_sections(report_id, th)
    g = client.post(f"/api/v1/reports/{report_id}/iep/goals", headers=th, json=GOAL_PAYLOAD).json()
    client.post(f"/api/v1/reports/{report_id}/submit", headers=th)
    client.post(f"/api/v1/reports/{report_id}/approve", headers=ah, json={})

    r = client.post(f"/api/v1/reports/{report_id}/iep/goals/{g['iep_goal_id']}/mark-achieved", headers=ah)
    assert r.status_code == 200
    assert r.json().get("lifecycle_status") == "achieved" or r.json().get("status") == "pending_review"


def test_iep_ai_suggestions_gated():
    therapist = _login("therapist@demo.com")
    th = {"Authorization": f"Bearer {therapist}"}
    report_id = _start_iep(th)
    r = client.post(f"/api/v1/reports/{report_id}/iep/generate-suggestions", headers=th)
    assert r.status_code == 403


def test_iep_available_goals_and_strategies():
    therapist = _login("therapist@demo.com")
    th = {"Authorization": f"Bearer {therapist}"}
    case_id = _case_id()
    r = client.get(f"/api/v1/cases/{case_id}/reports/iep/available-goals", headers=th)
    assert r.status_code == 200
    assert "repository_goals" in r.json()
    r = client.get(f"/api/v1/cases/{case_id}/reports/iep/available-strategies", headers=th)
    assert r.status_code == 200
    assert "items" in r.json()


def test_parent_clinical_iep_input():
    therapist = _login("therapist@demo.com")
    admin = _login("superadmin@demo.com")
    parent = _login("parent@demo.com")
    th = {"Authorization": f"Bearer {therapist}"}
    ah = {"Authorization": f"Bearer {admin}"}
    ph = {"Authorization": f"Bearer {parent}"}
    case_id = _case_id()
    report_id = _start_iep(th)
    _seed_iep_sections(report_id, th)
    client.post(f"/api/v1/reports/{report_id}/iep/goals", headers=th, json=GOAL_PAYLOAD)
    client.post(f"/api/v1/reports/{report_id}/submit", headers=th)
    client.post(f"/api/v1/reports/{report_id}/approve", headers=ah, json={})

    r = client.post(
        f"/api/v1/parent/cases/{case_id}/iep-inputs",
        headers=ph,
        json={"body": "Home routines are going well this month."},
    )
    assert r.status_code == 200, r.text
    assert "text" in r.json()
