"""Module admin can provision staff and new users land on correct admin homes."""

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


def test_module_admin_home_shows_module_admin_role():
    home = client.get("/api/v1/admin/home", headers=_login("moduleadmin@demo.com"))
    assert home.status_code == 200
    body = home.json()
    assert body["role"] == "MODULE_ADMIN"
    assert body["landing_route"] == "/admin"
    assert {w["id"] for w in body["widgets"]} >= {"logs", "reports", "billing"}


def test_module_admin_can_create_super_admin_and_case_manager():
    import time

    headers = _login("moduleadmin@demo.com")
    ts = int(time.time())
    sa_email = f"provision.sa.{ts}@demo.com"
    cm_email = f"provision.cm.{ts}@demo.com"

    sa = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": sa_email,
            "password": "demo123",
            "full_name": "Provisioned Super Admin",
            "role_names": ["SUPER_ADMIN"],
        },
    )
    assert sa.status_code == 201, sa.text

    cm = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": cm_email,
            "password": "demo123",
            "full_name": "Provisioned Case Manager",
            "role_names": ["CASE_MANAGER"],
            "module_access_grants": {
                "homecare": {"enabled": True, "access": "write"},
                "shadow_support": {"enabled": True, "access": "write"},
            },
        },
    )
    assert cm.status_code == 201, cm.text
    assert "homecare" in cm.json()["module_assignments"]

    sa_home = client.get("/api/v1/admin/home", headers=_login(sa_email))
    assert sa_home.status_code == 200
    assert sa_home.json()["role"] == "SUPER_ADMIN"
    assert sa_home.json()["landing_route"] == "/admin"

    cm_home = client.get("/api/v1/admin/home", headers=_login(cm_email))
    assert cm_home.status_code == 200
    assert cm_home.json()["role"] == "CASE_MANAGER"
    assert cm_home.json()["landing_route"] == "/admin/cm"

    cm_caseload = client.get("/api/v1/admin/cm/home", headers=_login(cm_email))
    assert cm_caseload.status_code == 200
