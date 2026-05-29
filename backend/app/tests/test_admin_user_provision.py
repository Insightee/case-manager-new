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


def test_admin_can_set_user_password_for_recovery():
    import time

    headers = _login("moduleadmin@demo.com")
    ts = int(time.time())
    email = f"recover.user.{ts}@demo.com"

    create = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": "demo123",
            "full_name": "Recover User",
            "role_names": ["THERAPIST"],
            "module_assignments": ["homecare"],
        },
    )
    assert create.status_code == 201, create.text
    user_id = create.json()["id"]

    set_pw = client.post(
        f"/api/v1/admin/users/{user_id}/set-password",
        headers=headers,
        json={"password": "newpass123"},
    )
    assert set_pw.status_code == 200, set_pw.text

    relogin = client.post("/api/v1/auth/login", json={"email": email, "password": "newpass123"})
    assert relogin.status_code == 200, relogin.text


def test_activate_for_login_succeeds_when_invite_email_raises(monkeypatch):
    import time

    headers = _login("moduleadmin@demo.com")
    ts = int(time.time())
    email = f"provision.activate.{ts}@demo.com"

    create = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": "demo123",
            "full_name": "Activate Target",
            "role_names": ["CASE_MANAGER"],
            "module_assignments": ["homecare"],
        },
    )
    assert create.status_code == 201, create.text
    user_id = create.json()["id"]

    deactivate = client.delete(f"/api/v1/admin/users/{user_id}", headers=headers)
    assert deactivate.status_code == 204, deactivate.text

    def _boom(*_args, **_kwargs):
        raise RuntimeError("smtp timeout simulated")

    monkeypatch.setattr(
        "app.services.user_provision_service.enqueue_portal_invite_email",
        _boom,
    )
    monkeypatch.setattr(
        "app.services.user_provision_service.enqueue_password_reset_email",
        _boom,
    )

    activate = client.post(f"/api/v1/admin/users/{user_id}/activate-for-login", headers=headers)
    assert activate.status_code == 200, activate.text
    body = activate.json()
    assert body["email"] == email
    assert body["user_active"] is True
    assert body["login_ready"] is True
    assert body["invite_sent"] is False

    invite = client.post(f"/api/v1/admin/users/{user_id}/invite-to-login", headers=headers)
    assert invite.status_code == 200, invite.text
    inv_body = invite.json()
    assert inv_body["email"] == email
    assert inv_body["user_active"] is True
    assert inv_body["invite_sent"] is False
    assert inv_body["invite_error"]
    assert inv_body["login_ready"] is True

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert login.status_code == 200, login.text


def test_inactive_user_cannot_login():
    import time

    headers = _login("moduleadmin@demo.com")
    ts = int(time.time())
    email = f"provision.inactive.{ts}@demo.com"

    create = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": "demo123",
            "full_name": "Inactive Target",
            "role_names": ["CASE_MANAGER"],
            "module_assignments": ["homecare"],
        },
    )
    assert create.status_code == 201, create.text
    user_id = create.json()["id"]

    client.delete(f"/api/v1/admin/users/{user_id}", headers=headers)

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert login.status_code == 401


def test_random_email_cannot_login():
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody.exists.99999@demo.com", "password": "demo123"},
    )
    assert login.status_code == 401


def test_invite_to_login_returns_email_and_status():
    import time

    headers = _login("moduleadmin@demo.com")
    ts = int(time.time())
    email = f"provision.invite.{ts}@demo.com"

    create = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": "demo123",
            "full_name": "Invite Target",
            "role_names": ["CASE_MANAGER"],
            "module_assignments": ["homecare"],
        },
    )
    assert create.status_code == 201, create.text
    user_id = create.json()["id"]

    invite = client.post(f"/api/v1/admin/users/{user_id}/invite-to-login", headers=headers)
    assert invite.status_code == 200, invite.text
    body = invite.json()
    assert body["email"] == email
    assert body["role"] == "CASE_MANAGER"
    assert "invite_status" in body
    assert body["user_active"] is True
