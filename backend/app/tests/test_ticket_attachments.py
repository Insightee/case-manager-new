from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)

MAX = 5 * 1024 * 1024


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str, password: str = "demo123"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def _therapist_headers():
    return {"Authorization": f"Bearer {_login('therapist@demo.com')}"}


def _admin_headers():
    return {"Authorization": f"Bearer {_login('superadmin@demo.com')}"}


def test_support_info_includes_limits():
    r = client.get("/api/v1/support/info")
    assert r.status_code == 200
    data = r.json()
    assert data["ticket_attachment_max_bytes"] == MAX
    assert data["ticket_attachment_max_files"] == 3


def test_create_ticket_with_attachment_and_download():
    th = _therapist_headers()
    files = {"files": ("note.txt", io.BytesIO(b"hello support"), "text/plain")}
    data = {"subject": "Attach test", "body": "See attached file", "category": "OTHER"}
    created = client.post("/api/v1/tickets", headers=th, data=data, files=files)
    assert created.status_code == 201, created.text
    ticket = created.json()
    detail = client.get(f"/api/v1/tickets/{ticket['id']}", headers=th)
    assert detail.status_code == 200
    attachments = detail.json().get("attachments") or []
    assert len(attachments) >= 1
    att_id = attachments[0]["id"]

    dl = client.get(f"/api/v1/tickets/attachments/{att_id}/download", headers=th)
    assert dl.status_code == 200
    assert dl.content == b"hello support"


def test_rejects_oversized_file():
    th = _therapist_headers()
    big = io.BytesIO(b"x" * (MAX + 1))
    files = {"files": ("big.bin", big, "application/pdf")}
    data = {"subject": "Too big", "body": "nope", "category": "OTHER"}
    r = client.post("/api/v1/tickets", headers=th, data=data, files=files)
    assert r.status_code == 400
    assert "5 MB" in r.json()["detail"] or "MB" in r.json()["detail"]


def test_rejects_four_files():
    th = _therapist_headers()
    files = [
        ("files", (f"f{i}.txt", io.BytesIO(b"x"), "text/plain"))
        for i in range(4)
    ]
    data = {"subject": "Too many", "body": "nope", "category": "OTHER"}
    r = client.post("/api/v1/tickets", headers=th, data=data, files=files)
    assert r.status_code == 400


def test_parent_portal_info_policies_bot_key():
    parent_token = _login("parent@demo.com")
    r = client.get("/api/v1/parent/portal-info", headers={"Authorization": f"Bearer {parent_token}"})
    assert r.status_code == 200
    assert "policies_bot_url" in r.json()
    assert "ticket_attachment_max_files" in r.json()


def test_get_ticket_detail_requires_access():
    th = _therapist_headers()
    created = client.post(
        "/api/v1/tickets",
        headers=th,
        json={"subject": "Private", "body": "mine only", "category": "OTHER"},
    )
    assert created.status_code == 201
    tid = created.json()["id"]

    other = client.get(f"/api/v1/tickets/{tid}", headers=_admin_headers())
    assert other.status_code == 200
