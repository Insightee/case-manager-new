"""IEP v2 suggestions and approve workflow."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.iep_plan import IepPlan, IepPlanStatus

client = TestClient(app)
ensure_sqlite_schema_patches()


def _reset_iep_plan(db, case_id: int) -> None:
    plan = db.scalars(select(IepPlan).where(IepPlan.case_id == case_id).order_by(IepPlan.id.desc())).first()
    if plan:
        plan.status = IepPlanStatus.DRAFT.value
        db.commit()


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_iep_suggestion_and_resolve():
    admin_token = _login("superadmin@demo.com")
    parent_token = _login("parent@demo.com")

    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        case_id = case.id
        _reset_iep_plan(db, case_id)

    admin_h = {"Authorization": f"Bearer {admin_token}"}
    sections = {
        "schema_version": 2,
        "header": {"child_name": "Test", "about_child_brief": "Brief"},
        "challenges": "Focus areas",
        "observations": "Observed engagement",
        "verification": {"therapist_verified": True, "therapist_name": "Dr. T"},
    }
    r = client.put(f"/api/v1/admin/cases/{case_id}/iep-plan", headers=admin_h, json={"sections": sections})
    assert r.status_code == 200

    r = client.post(f"/api/v1/admin/cases/{case_id}/iep-plan/share-with-parent", headers=admin_h)
    assert r.status_code == 200

    parent_h = {"Authorization": f"Bearer {parent_token}"}
    r = client.post(
        f"/api/v1/parent/cases/{case_id}/iep-plan/suggestions",
        headers=parent_h,
        json={"body": "Please add more detail on social goals."},
    )
    assert r.status_code == 200
    assert any(s["body"].startswith("Please add") for s in r.json()["suggestions"])

    r = client.get(f"/api/v1/admin/cases/{case_id}/iep-plan", headers=admin_h)
    assert r.status_code == 200
    assert r.json()["status"] == "EDITS_SUGGESTED"

    r = client.post(f"/api/v1/admin/cases/{case_id}/iep-plan/suggestions/resolve", headers=admin_h)
    assert r.status_code == 200
    assert r.json()["status"] == "DRAFT"

    r = client.get(f"/api/v1/admin/cases/{case_id}/iep-plan/preview", headers=admin_h)
    assert r.status_code == 200
    assert "html" in r.json()
    assert "Test" in r.json()["html"]
