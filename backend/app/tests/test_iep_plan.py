"""IEP plan builder and parent share."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case

client = TestClient(app)
ensure_sqlite_schema_patches()


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

    headers = {"Authorization": f"Bearer {admin_token}"}
    sections = {
        "about_child": "Aarav is a bright student.",
        "referral": "Referred for shadow support.",
        "observations": "Engaged in classroom activities.",
        "learning_environments": [
            {"environment": "School", "strengths": "Peer interaction", "supports_needed": "Visual schedule"},
        ],
        "interventions": "Weekly shadow sessions.",
        "signatures": "Case manager — Insighte",
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
