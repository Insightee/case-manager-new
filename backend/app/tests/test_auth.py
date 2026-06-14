from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "smtp_configured" in body
    assert isinstance(body["smtp_configured"], bool)


def test_login_and_me():
    r = client.post("/api/v1/auth/login", json={"email": "therapist@demo.com", "password": "demo123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert "THERAPIST" in me.json()["roles"]


def test_login_without_portal_still_works():
    r = client.post("/api/v1/auth/login", json={"email": "therapist@demo.com", "password": "demo123"})
    assert r.status_code == 200


def test_login_portal_therapist_accepts_therapist():
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "therapist@demo.com", "password": "demo123", "portal": "therapist"},
    )
    assert r.status_code == 200


def test_login_portal_rejects_therapist_on_client_portal():
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "therapist@demo.com", "password": "demo123", "portal": "parent"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "Invalid Login. Use the correct portal."


def test_login_portal_rejects_parent_on_staff_portal():
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "parent@demo.com", "password": "demo123", "portal": "staff"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "Invalid Login. Use the correct portal."


def test_login_portal_accepts_parent_on_client_portal():
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "parent@demo.com", "password": "demo123", "portal": "parent"},
    )
    assert r.status_code == 200


def test_login_portal_accepts_superadmin_on_staff_portal():
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@demo.com", "password": "demo123", "portal": "staff"},
    )
    assert r.status_code == 200


def test_login_portal_rejects_superadmin_on_client_portal():
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@demo.com", "password": "demo123", "portal": "parent"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "Invalid Login. Use the correct portal."


def test_login_portal_admin_alias_maps_to_staff():
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "finance@demo.com", "password": "demo123", "portal": "admin"},
    )
    assert r.status_code == 200


def test_login_remember_me_extends_refresh_token():
    from datetime import datetime, timezone

    from app.core.security import decode_refresh_token

    short = client.post(
        "/api/v1/auth/login",
        json={"email": "parent@demo.com", "password": "demo123", "remember_me": False},
    )
    long = client.post(
        "/api/v1/auth/login",
        json={"email": "parent@demo.com", "password": "demo123", "remember_me": True},
    )
    assert short.status_code == 200
    assert long.status_code == 200
    short_exp = decode_refresh_token(short.json()["refresh_token"])["exp"]
    long_exp = decode_refresh_token(long.json()["refresh_token"])["exp"]
    if isinstance(short_exp, datetime):
        short_ts = short_exp.timestamp()
        long_ts = long_exp.timestamp()
    else:
        short_ts = float(short_exp)
        long_ts = float(long_exp)
    assert long_ts > short_ts
    assert decode_refresh_token(long.json()["refresh_token"]).get("remember") is True


def test_parent_cannot_see_internal_reports():
    r = client.post("/api/v1/auth/login", json={"email": "parent@demo.com", "password": "demo123"})
    token = r.json()["access_token"]
    reports = client.get("/api/v1/parent/reports", headers={"Authorization": f"Bearer {token}"})
    assert reports.status_code == 200
    for report in reports.json():
        assert str(report["status"]).upper() not in (
            "DRAFT",
            "UNDER_REVIEW",
            "REJECTED",
            "INTERNAL_ONLY",
        )
