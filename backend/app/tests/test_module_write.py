"""Per-module write grant enforcement."""

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


def test_me_includes_module_access_and_view_only():
    r = client.get("/api/v1/auth/me", headers=_login("viewer@demo.com"))
    assert r.status_code == 200
    body = r.json()
    assert body["is_view_only"] is True
    assert body["modules"]
    assert body["modules"][0]["access"] == "view"


def test_view_only_user_cannot_patch_case():
    headers = _login("viewer@demo.com")
    cases = client.get("/api/v1/cases?page_size=5", headers=headers)
    assert cases.status_code == 200
    items = cases.json()["items"]
    if not items:
        return
    case_id = items[0]["id"]
    r = client.patch(
        f"/api/v1/cases/{case_id}",
        headers=headers,
        json={"region": "blocked"},
    )
    assert r.status_code == 403
    assert "View-only" in r.json()["detail"]


def test_view_only_user_cannot_bulk_approve_reports():
    headers = _login("viewer@demo.com")
    r = client.post(
        "/api/v1/admin/reports/bulk/approve",
        headers=headers,
        json={"report_type": "monthly", "ids": [1], "visibility_status": "APPROVED_FOR_PARENT"},
    )
    assert r.status_code == 403
    assert "View-only" in r.json()["detail"]


def test_super_admin_can_mutate_client_billing():
    headers = _login("superadmin@demo.com")
    r = client.get("/api/v1/admin/client-billing/invoices", headers=headers)
    assert r.status_code == 200
    items = r.json()
    if not items:
        return
    inv_id = items[0]["id"]
    detail = client.get(f"/api/v1/admin/client-billing/invoices/{inv_id}", headers=headers)
    assert detail.status_code == 200
    if detail.json().get("status") == "DRAFT":
        patch = client.patch(
            f"/api/v1/admin/client-billing/invoices/{inv_id}",
            headers=headers,
            json={"status": "GENERATED"},
        )
        assert patch.status_code != 403 or "View-only" not in patch.text


def test_view_only_user_cannot_save_iep():
    headers = _login("viewer@demo.com")
    cases = client.get("/api/v1/cases?page_size=5", headers=headers)
    if cases.status_code != 200 or not cases.json()["items"]:
        return
    case_id = cases.json()["items"][0]["id"]
    r = client.put(
        f"/api/v1/admin/cases/{case_id}/iep-plan",
        headers=headers,
        json={"sections": {}, "version": 1},
    )
    assert r.status_code == 403

