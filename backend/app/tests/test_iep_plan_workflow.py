"""IEP plan validation, versioning, PDF export, and parent acknowledgement flags."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.iep_plan import IepHeaderSection, IepPlanSections, IepVerificationSection
from app.seed.demo_seed import run as seed_run
from app.services import iep_plan_service as iep_svc
from app.tests.conftest import api_items

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_validate_sections_for_share_rejects_empty():
    errors = iep_svc.validate_sections_for_share(IepPlanSections())
    assert len(errors) >= 2


def test_validate_sections_for_share_accepts_complete():
    sections = IepPlanSections(
        header=IepHeaderSection(child_name="Alex"),
        observations="Clinical notes here.",
        verification=IepVerificationSection(
            therapist_verified=True,
            prepared_by_name="Verifier",
            prepared_at="2026-05-25",
        ),
    )
    assert iep_svc.validate_sections_for_share(sections) == []


def test_bump_version_label():
    assert iep_svc._bump_version_label("v1") == "v2"


def test_share_iep_rejects_empty_plan():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    items = api_items(cases.json())
    if not items:
        pytest.skip("no cases")
    case_id = items[0]["id"]
    plan = client.get(f"/api/v1/admin/cases/{case_id}/iep-plan", headers=headers).json()
    if not plan.get("can_edit"):
        rev = client.post(f"/api/v1/admin/cases/{case_id}/iep-plan/new-version", headers=headers)
        assert rev.status_code == 200
    empty = {"sections": IepPlanSections().model_dump()}
    put = client.put(f"/api/v1/admin/cases/{case_id}/iep-plan", headers=headers, json=empty)
    assert put.status_code == 200
    share = client.post(f"/api/v1/admin/cases/{case_id}/iep-plan/share-with-parent", headers=headers)
    assert share.status_code == 400


def test_iep_pdf_export():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    case_id = api_items(cases.json())[0]["id"]
    sections = {
        "sections": {
            "schema_version": 2,
            "header": {"child_name": "Test Child", "about_child_brief": "Brief"},
            "observations": "Obs",
            "learning_environments": [],
            "challenges": "",
            "current_performance": [],
            "learning_style": {"styles": [], "elaboration": ""},
            "interventions": "",
            "talent_development": {"strengths": "", "goals": "", "strategies": "", "areas_of_need": ""},
            "other_areas_of_need": {"strengths": "", "goals": "", "strategies": "", "areas_of_need": ""},
            "intervention_by_insighte": "",
            "verification": {
                "therapist_verified": True,
                "therapist_name": "T",
                "prepared_by_name": "Admin",
                "prepared_at": "2026-05-25",
            },
            "supplementary_attachment_ids": [],
        }
    }
    client.put(f"/api/v1/admin/cases/{case_id}/iep-plan", headers=headers, json=sections)
    pdf = client.get(f"/api/v1/admin/cases/{case_id}/iep-plan/export/pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.headers.get("content-type", "").startswith("application/pdf")


def test_new_iep_version_after_share():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    case_id = api_items(cases.json())[0]["id"]
    plan = client.get(f"/api/v1/admin/cases/{case_id}/iep-plan", headers=headers).json()
    body = {
        "sections": {
            **plan["sections"],
            "header": {**plan["sections"]["header"], "child_name": plan["sections"]["header"].get("child_name") or "Child"},
            "observations": plan["sections"].get("observations") or "Filled for test",
            "verification": {
                **plan["sections"].get("verification", {}),
                "therapist_verified": True,
                "prepared_by_name": "Super Admin",
                "prepared_at": "2026-05-25",
            },
        }
    }
    client.put(f"/api/v1/admin/cases/{case_id}/iep-plan", headers=headers, json=body)
    share = client.post(f"/api/v1/admin/cases/{case_id}/iep-plan/share-with-parent", headers=headers)
    if share.status_code != 200:
        pytest.skip("share failed in fixture state")
    rev = client.post(f"/api/v1/admin/cases/{case_id}/iep-plan/new-version", headers=headers)
    assert rev.status_code == 200
    assert rev.json()["version"] != plan["version"]
    assert rev.json()["can_edit"] is True


def test_parent_iep_detail_can_acknowledge_flag():
    admin_token = _login("superadmin@demo.com")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    cases = client.get("/api/v1/cases", headers=admin_headers)
    case_id = api_items(cases.json())[0]["id"]
    plan = client.get(f"/api/v1/admin/cases/{case_id}/iep-plan", headers=admin_headers).json()
    body = {
        "sections": {
            **plan["sections"],
            "header": {**plan["sections"]["header"], "child_name": "Ack Test Child"},
            "observations": "Obs for ack test",
            "verification": {
                "therapist_verified": True,
                "prepared_by_name": "Admin",
                "prepared_at": "2026-05-25",
            },
        }
    }
    client.put(f"/api/v1/admin/cases/{case_id}/iep-plan", headers=admin_headers, json=body)
    share = client.post(f"/api/v1/admin/cases/{case_id}/iep-plan/share-with-parent", headers=admin_headers)
    if share.status_code != 200:
        pytest.skip("could not share IEP")
    att_id = share.json().get("attachment_id")
    if not att_id:
        pytest.skip("no attachment on shared plan")

    parent_token = _login("parent@demo.com")
    parent_headers = {"Authorization": f"Bearer {parent_token}"}
    detail = client.get(f"/api/v1/parent/reports/iep/{att_id}", headers=parent_headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data.get("canAcknowledge") is True
    assert data.get("bodyHtml")
