"""Admin invite revoke and related provisioning flows."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.user import InviteToken
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


"""Admin invite revoke and related provisioning flows."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.user import InviteToken
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_pending_invite(email: str, role_name: str = "CASE_MANAGER") -> InviteToken:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        token = secrets.token_urlsafe(16)
        inv = InviteToken(
            email=email,
            role_name=role_name,
            module_assignments=[],
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return inv


def _staff_invite_payload(email: str, role_name: str = "CASE_MANAGER") -> dict:
    return {
        "email": email,
        "role_name": role_name,
        "send_email": False,
        "module_assignments": ["homecare"],
    }


def test_invite_cap_blocks_third_pending():
    headers = _login("superadmin@demo.com")
    email = f"cap.test.{secrets.token_hex(4)}@demo.com"
    _create_pending_invite(email)
    _create_pending_invite(email)

    res = client.post(
        "/api/v1/admin/therapists/invite",
        headers=headers,
        json=_staff_invite_payload(email),
    )
    assert res.status_code == 400
    assert "Maximum invites sent" in res.json()["detail"]


def test_revoke_then_new_invite_allowed():
    headers = _login("superadmin@demo.com")
    email = f"revoke.cap.{secrets.token_hex(4)}@demo.com"
    inv1 = _create_pending_invite(email)
    _create_pending_invite(email)

    revoke = client.post(f"/api/v1/admin/invites/{inv1.id}/revoke", headers=headers)
    assert revoke.status_code == 200

    res = client.post(
        "/api/v1/admin/therapists/invite",
        headers=headers,
        json=_staff_invite_payload(email),
    )
    assert res.status_code == 200
    assert res.json().get("invite_url")


def test_cross_role_invite_blocked():
    headers = _login("superadmin@demo.com")
    email = f"cross.role.{secrets.token_hex(4)}@demo.com"
    _create_pending_invite(email, role_name="THERAPIST")

    res = client.post(
        "/api/v1/admin/therapists/invite",
        headers=headers,
        json=_staff_invite_payload(email, "CASE_MANAGER"),
    )
    assert res.status_code == 400
    assert "Pending invite exists" in res.json()["detail"]


def test_bulk_user_status_and_invite_revoke():
    headers = _login("superadmin@demo.com")
    email = f"bulk.test.{secrets.token_hex(4)}@demo.com"
    inv = _create_pending_invite(email)

    bulk_revoke = client.post(
        "/api/v1/admin/invites/bulk-revoke",
        headers=headers,
        json={"invite_ids": [inv.id]},
    )
    assert bulk_revoke.status_code == 200
    assert bulk_revoke.json()["revoked"] == 1

    from app.core.database import SessionLocal

    with SessionLocal() as db:
        row = db.scalars(select(InviteToken).where(InviteToken.id == inv.id)).first()
        assert row is None

    # Deactivate a seeded staff user then bulk-activate
    staff = client.get("/api/v1/admin/users?page_size=5", headers=headers).json()
    items = staff.get("items") or staff
    target = next((u for u in items if u.get("email") == "admin@demo.com"), None)
    if target:
        client.delete(f"/api/v1/admin/users/{target['id']}", headers=headers)
        bulk = client.post(
            "/api/v1/admin/users/bulk-status",
            headers=headers,
            json={"user_ids": [target["id"]], "is_active": True},
        )
        assert bulk.status_code == 200
        assert bulk.json()["updated"] == 1


def test_revoke_invite_blocks_preview():
    headers = _login("superadmin@demo.com")
    email = f"revoke.test.{secrets.token_hex(4)}@demo.com"
    inv = _create_pending_invite(email)

    preview = client.get(f"/api/v1/auth/invite/{inv.token}/preview")
    assert preview.status_code == 200

    revoke = client.post(f"/api/v1/admin/invites/{inv.id}/revoke", headers=headers)
    assert revoke.status_code == 200
    assert revoke.json()["ok"] is True

    preview_after = client.get(f"/api/v1/auth/invite/{inv.token}/preview")
    assert preview_after.status_code == 404

    from app.core.database import SessionLocal

    with SessionLocal() as db:
        row = db.scalars(select(InviteToken).where(InviteToken.id == inv.id)).first()
        assert row is None


def test_revoke_used_invite_rejected():
    headers = _login("superadmin@demo.com")
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        inv = db.scalars(select(InviteToken).where(InviteToken.used_at.isnot(None)).limit(1)).first()
        if not inv:
            return
        invite_id = inv.id

    res = client.post(f"/api/v1/admin/invites/{invite_id}/revoke", headers=headers)
    assert res.status_code == 400


def test_next_case_code_generated():
    headers = _login("superadmin@demo.com")
    res = client.get("/api/v1/admin/cases/next-code?product_module=homecare", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["case_code"]
    assert isinstance(body["case_code"], str)


def test_homecare_service_filter_expects_multiple_categories():
    """Homecare program should offer clinical service types beyond the homecare line itself."""
    headers = _login("superadmin@demo.com")
    cats = client.get("/api/v1/admin/service-categories", headers=headers).json()
    shadow = "shadow_support"

    def matches(cat, module):
        ids = [str(m.get("id", "")).lower() for m in (cat.get("product_modules") or [])]
        if not ids:
            ids = [str(cat.get("id", "")).lower()]
        if module in ids:
            return True
        if module == shadow:
            return cat.get("id") == shadow or shadow in ids
        if module == "homecare":
            return cat.get("id") != shadow and not all(i == shadow for i in ids)
        return cat.get("id") == module

    homecare = [c for c in cats if matches(c, "homecare")]
    shadow_only = [c for c in cats if matches(c, shadow)]
    assert len(homecare) >= 5, f"expected multiple homecare services, got {len(homecare)}"
    assert len(shadow_only) == 1


def test_service_categories_include_product_modules():
    headers = _login("superadmin@demo.com")
    res = client.get("/api/v1/admin/service-categories", headers=headers)
    assert res.status_code == 200
    rows = res.json()
    assert isinstance(rows, list)
    for cat in rows:
        assert "product_modules" in cat
        mods = cat.get("product_modules") or []
        if mods:
            assert all("id" in m and "label" in m for m in mods)
