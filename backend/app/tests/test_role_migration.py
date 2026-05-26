"""Phase A: assignable roles and demo migration."""

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


def test_rbac_catalog_excludes_legacy_admin():
    r = client.get("/api/v1/admin/rbac/catalog", headers=_login("moduleadmin@demo.com"))
    assert r.status_code == 200
    role_ids = {row["id"] for row in r.json()["assignable_roles"]}
    assert "MODULE_ADMIN" in role_ids
    assert "ADMIN" not in role_ids
    assert r.json()["deprecated_roles"] == ["SUPERVISOR", "VIEWER"]


def test_cannot_create_user_with_viewer_role():
    headers = _login("moduleadmin@demo.com")
    r = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "bad.viewer@demo.com",
            "password": "demo123",
            "full_name": "Bad Viewer",
            "role_names": ["VIEWER"],
            "module_access_grants": {"homecare": {"enabled": True, "access": "view"}},
        },
    )
    assert r.status_code == 400
    assert "retired" in r.json()["detail"].lower()


def test_cannot_create_user_with_legacy_admin_role():
    headers = _login("moduleadmin@demo.com")
    r = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "bad.admin@demo.com",
            "password": "demo123",
            "full_name": "Bad Admin",
            "role_names": ["ADMIN"],
            "module_access_grants": {"homecare": {"enabled": True, "access": "write"}},
        },
    )
    assert r.status_code == 400
    assert "MODULE_ADMIN" in r.json()["detail"]
