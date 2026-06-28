"""Clinical Brain strategy pool admin API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.tests.conftest import login_headers

client = TestClient(app)


def test_admin_create_strategy_pool():
    headers = login_headers(client, "superadmin@demo.com")
    r = client.post(
        "/api/v1/admin/strategy-pool",
        headers=headers,
        json={
            "label": "Quiet corner preview",
            "domain_key": "emotional_regulation",
            "when_to_use": "Before noisy transitions",
            "metadata": {"support_need": "transitions", "support_level": "visual_support"},
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["label"] == "Quiet corner preview"


def test_therapist_cannot_create_org_strategy():
    headers = login_headers(client, "therapist@demo.com")
    r = client.post(
        "/api/v1/admin/strategy-pool",
        headers=headers,
        json={"label": "Should fail pool create", "domain_key": "communication"},
    )
    assert r.status_code == 403


def test_deprecate_excluded_from_matches():
    from app.core.database import SessionLocal
    from app.services import goal_repository_service as repo_svc
    from app.services import strategy_pool_matching_service as match_svc
    from app.tests.conftest import api_first_case_id

    admin_headers = login_headers(client, "superadmin@demo.com")
    created = client.post(
        "/api/v1/admin/strategy-pool",
        headers=admin_headers,
        json={
            "label": "Deprecate me strategy",
            "domain_key": "communication",
            "activate": True,
        },
    )
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    dep = client.post(f"/api/v1/admin/strategy-pool/{sid}/deprecate", headers=admin_headers)
    assert dep.status_code == 200, dep.text

    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    with SessionLocal() as db:
        ids = [m["id"] for m in match_svc.match_strategy_pool(db, case_id, limit=100)]
    assert sid not in ids
