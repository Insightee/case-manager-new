"""IEP plan builder and parent share."""
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


def test_iep_plan_save_and_share_with_parent():
    admin_token = _login("superadmin@demo.com")

    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        case_id = case.id
        _reset_iep_plan(db, case_id)

    headers = {"Authorization": f"Bearer {admin_token}"}
    sections = {
        "schema_version": 2,
        "header": {"child_name": "Aarav M.", "about_child_brief": "Bright student."},
        "observations": "Engaged in classroom activities.",
        "learning_environments": [
            {"environment": "School", "strengths": "Peer interaction", "supports_needed": "Visual schedule"},
        ],
        "challenges": "",
        "current_performance": [],
        "learning_style": {"styles": [], "elaboration": ""},
        "interventions": "Weekly shadow sessions.",
        "talent_development": {"strengths": "", "goals": "", "strategies": "", "areas_of_need": ""},
        "other_areas_of_need": {"strengths": "", "goals": "", "strategies": "", "areas_of_need": ""},
        "intervention_by_insighte": "",
        "verification": {
            "therapist_verified": True,
            "therapist_name": "Therapist Neha",
            "prepared_by_name": "Super Admin",
            "prepared_at": "2026-05-25",
        },
        "supplementary_attachment_ids": [],
    }
    r = client.put(
        f"/api/v1/admin/cases/{case_id}/iep-plan",
        headers=headers,
        json={"sections": sections, "version": "v1"},
    )
    assert r.status_code == 200

    r = client.post(f"/api/v1/admin/cases/{case_id}/iep-plan/share-with-parent", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "SHARED_WITH_PARENT"

    parent_token = _login("parent@demo.com")
    r = client.get("/api/v1/parent/reports/hub", headers={"Authorization": f"Bearer {parent_token}"})
    assert r.status_code == 200
    iep_items = [i for i in r.json().get("iep", []) if str(i.get("caseDbId")) == str(case_id)]
    assert len(iep_items) >= 1

    iep_id = iep_items[0]["id"]
    r = client.get(f"/api/v1/parent/reports/iep/{iep_id}", headers={"Authorization": f"Bearer {parent_token}"})
    assert r.status_code == 200
    assert r.json()["status"] in ("pending", "acknowledged")

    r = client.post(
        f"/api/v1/parent/reports/iep/{iep_id}/acknowledge",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert r.status_code == 200
