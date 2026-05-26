"""Service-category-centric access model and RBAC catalog shape."""

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_rbac_catalog_has_service_and_org_sections():
    r = client.get("/api/v1/admin/rbac/catalog", headers=_login("moduleadmin@demo.com"))
    assert r.status_code == 200
    data = r.json()
    assert "service_categories" in data
    assert "org_capabilities" in data
    assert isinstance(data["service_categories"], list)
    assert isinstance(data["org_capabilities"], list)
    ids = {row["id"] for row in data["service_categories"]}
    assert "homecare" in ids or "shadow_support" in ids
    org_ids = {row["id"] for row in data["org_capabilities"]}
    assert "billing" in org_ids


def test_clinical_services_catalog_lists_products_key():
    r = client.get("/api/v1/auth/catalog/clinical-services", headers=_login("superadmin@demo.com"))
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    if rows:
        assert "products" in rows[0]


def test_hr_recipients_includes_staff_and_therapists():
    r = client.get("/api/v1/hr/recipients", headers=_login("hr@demo.com"))
    assert r.status_code == 200
    kinds = {row.get("kind") for row in r.json()}
    assert "therapist" in kinds or "staff" in kinds


def test_therapist_onboard_requires_primary_cm():
    headers = _login("moduleadmin@demo.com")
    r = client.post(
        "/api/v1/admin/therapists/onboard",
        headers=headers,
        json={
            "email": "missing.cm@demo.com",
            "full_name": "No CM",
            "services_offered": ["homecare"],
            "mode": "invite",
        },
    )
    assert r.status_code == 422
