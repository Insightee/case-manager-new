"""Parent portal invite rotation and bulk re-invite for awaiting-login parents."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.user import InviteToken
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _login(email: str = "superadmin@demo.com") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_parent_with_invite(headers: dict) -> dict:
    import uuid

    suffix = uuid.uuid4().hex[:8]
    email = f"rotate-parent-{suffix}@demo.com"
    fam = client.post(
        "/api/v1/admin/families",
        headers=headers,
        json={
            "parent_email": email,
            "parent_full_name": "Rotate Parent",
            "child": {"first_name": "Rotate", "last_name": suffix},
            "send_invite": True,
        },
    )
    assert fam.status_code == 201, fam.text
    body = fam.json()
    child_id = body["childId"]
    case = client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "child_id": child_id,
            "service_type": "Invite test",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_rate_per_session_inr": 1000,
            "pay_share_amount_inr": 600,
        },
    )
    assert case.status_code == 201, case.text
    return {
        "email": email,
        "parent_user_id": body["parentUserId"],
        "child_id": child_id,
        "invite_url": body["inviteUrl"],
    }


def _expire_invites_for_email(email: str) -> None:
    db = SessionLocal()
    try:
        rows = db.scalars(select(InviteToken).where(InviteToken.email == email.lower())).all()
        past = datetime.now(timezone.utc) - timedelta(days=2)
        for inv in rows:
            inv.expires_at = past
        db.commit()
    finally:
        db.close()


def test_invite_to_login_rotates_expired_parent_invite():
    headers = _login()
    created = _create_parent_with_invite(headers)
    old_token = created["invite_url"].rstrip("/").split("/")[-1]
    _expire_invites_for_email(created["email"])

    families_before = client.get("/api/v1/admin/families", headers=headers)
    row = next(r for r in families_before.json() if r["childId"] == created["child_id"])
    assert row["pendingInvite"]["isExpired"] is True
    assert "inviteUrl" not in row["pendingInvite"]

    invite = client.post(
        f"/api/v1/admin/users/{created['parent_user_id']}/invite-to-login",
        headers=headers,
    )
    assert invite.status_code == 200, invite.text
    body = invite.json()
    assert body.get("invite_url"), body
    assert "/invite/" in body["invite_url"]
    new_token = body["invite_url"].rstrip("/").split("/")[-1]
    assert new_token != old_token

    preview_old = client.get(f"/api/v1/auth/invite/{old_token}/preview")
    assert preview_old.status_code in (400, 404)

    preview_new = client.get(f"/api/v1/auth/invite/{new_token}/preview")
    assert preview_new.status_code == 200, preview_new.text


def test_resend_expired_invite_rotates_token():
    headers = _login()
    created = _create_parent_with_invite(headers)
    old_token = created["invite_url"].rstrip("/").split("/")[-1]
    _expire_invites_for_email(created["email"])

    db = SessionLocal()
    try:
        inv = db.scalars(
            select(InviteToken).where(
                InviteToken.email == created["email"].lower(),
                InviteToken.used_at.is_(None),
            )
        ).first()
        invite_id = inv.id
    finally:
        db.close()

    resend = client.post(
        f"/api/v1/admin/invites/{invite_id}/resend-email?force_resend=true",
        headers=headers,
    )
    assert resend.status_code == 200, resend.text
    body = resend.json()
    assert body.get("invite_url")
    new_token = body["invite_url"].rstrip("/").split("/")[-1]
    assert new_token != old_token

    preview_new = client.get(f"/api/v1/auth/invite/{new_token}/preview")
    assert preview_new.status_code == 200


def test_parents_awaiting_login_includes_unlogged_parent():
    headers = _login()
    created = _create_parent_with_invite(headers)
    _expire_invites_for_email(created["email"])

    awaiting = client.get("/api/v1/admin/families/parents-awaiting-login", headers=headers)
    assert awaiting.status_code == 200, awaiting.text
    payload = awaiting.json()
    assert payload["count"] >= 1
    emails = {row["parentEmail"] for row in payload["items"]}
    assert created["email"] in emails


def test_bulk_invite_parents_awaiting_login():
    headers = _login()
    created = _create_parent_with_invite(headers)
    _expire_invites_for_email(created["email"])

    bulk = client.post(
        "/api/v1/admin/families/bulk-invite-parents",
        headers=headers,
        json={"user_ids": [created["parent_user_id"]]},
    )
    assert bulk.status_code == 200, bulk.text
    body = bulk.json()
    assert body["sent"] >= 1
