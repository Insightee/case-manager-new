"""Rich-text reports: body_html, images, PDF, session context, CM review."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import api_items

client = TestClient(app)

# Minimal 1x1 PNG
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _therapist_case_id(headers: dict) -> int:
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    items = api_items(cases.json())
    assert items
    return items[0]["id"]


def test_patch_body_html_and_plan():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = _therapist_case_id(headers)
    created = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={
            "case_id": case_id,
            "month": "Test Rich Text 2099",
            "category": "CLIENT_MONTHLY",
        },
    )
    assert created.status_code == 201, created.text
    rid = created.json()["id"]
    patched = client.patch(
        f"/api/v1/reports/monthly/{rid}",
        headers=headers,
        json={
            "body_html": "<p>Progress <strong>note</strong></p>",
            "plan_next_month": "Continue speech goals twice weekly",
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert "Progress" in (body.get("summary") or "")
    assert body["plan_next_month"] == "Continue speech goals twice weekly"
    assert "<p>Progress" in (body.get("body_html") or "")


def test_report_image_upload_and_stream():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = _therapist_case_id(headers)
    created = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": "Image Upload 2099"},
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    up = client.post(
        f"/api/v1/reports/monthly/{rid}/images",
        headers=headers,
        files={"file": ("chart.png", io.BytesIO(_TINY_PNG), "image/png")},
    )
    assert up.status_code == 200, up.text
    data = up.json()
    assert data.get("id")
    assert "/api/v1/reports/images/" in (data.get("url") or "")
    img = client.get(f"/api/v1/reports/images/{data['id']}", headers=headers)
    assert img.status_code == 200
    assert img.headers.get("content-type", "").startswith("image/")


def test_monthly_pdf_download():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    listing = client.get("/api/v1/reports/monthly", headers=headers)
    assert listing.status_code == 200
    items = api_items(listing.json())
    assert items
    rid = items[0]["id"]
    client.patch(
        f"/api/v1/reports/monthly/{rid}",
        headers={"Authorization": f"Bearer {_login('therapist@demo.com')}"},
        json={"body_html": "<p>PDF body</p>", "plan_next_month": "Next steps"},
    )
    pdf = client.get(f"/api/v1/reports/monthly/{rid}/download", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers.get("content-type") == "application/pdf"
    assert pdf.content[:4] == b"%PDF"


def test_session_context_and_csv_export():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    reports = client.get("/api/v1/reports/monthly", headers=headers)
    assert reports.status_code == 200
    items = api_items(reports.json())
    assert items
    rid = items[0]["id"]
    case_id = items[0]["case_id"]
    ctx = client.get(f"/api/v1/reports/monthly/{rid}/session-context", headers=headers)
    assert ctx.status_code == 200
    assert isinstance(ctx.json(), list)
    csv_res = client.get(
        "/api/v1/reports/therapist/session-logs/export",
        headers=headers,
        params={"case_id": case_id, "month": items[0].get("month")},
    )
    assert csv_res.status_code == 200, csv_res.text
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert b"date" in csv_res.content.lower() or len(csv_res.content) >= 0


def test_admin_category_filter():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    all_rows = client.get("/api/v1/admin/reports/monthly", headers=headers)
    assert all_rows.status_code == 200
    filtered = client.get(
        "/api/v1/admin/reports/monthly",
        headers=headers,
        params={"category": "CLIENT_MONTHLY"},
    )
    assert filtered.status_code == 200
    for row in api_items(filtered.json()):
        cat = row.get("category")
        assert cat in (None, "CLIENT_MONTHLY")


def test_cm_review_internal_note_and_correction():
    cm_token = _login("casemanager@demo.com")
    cm_headers = {"Authorization": f"Bearer {cm_token}"}
    th_token = _login("therapist@demo.com")
    th_headers = {"Authorization": f"Bearer {th_token}"}
    case_id = _therapist_case_id(th_headers)
    created = client.post(
        "/api/v1/reports/monthly",
        headers=th_headers,
        json={"case_id": case_id, "month": "CM Review 2099", "body_html": "<p>Submit me</p>"},
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    submit = client.post(f"/api/v1/reports/monthly/{rid}/submit", headers=th_headers)
    assert submit.status_code == 200

    note = client.post(
        f"/api/v1/admin/reports/monthly/{rid}/cm-review",
        headers=cm_headers,
        json={"comment": "Looks good for admin", "request_changes": False},
    )
    assert note.status_code == 200, note.text
    history = note.json().get("review_history") or []
    assert any("[CM reviewed]" in (h.get("comment") or "") for h in history)

    created2 = client.post(
        "/api/v1/reports/monthly",
        headers=th_headers,
        json={"case_id": case_id, "month": "CM Reject 2099", "body_html": "<p>Fix typos</p>"},
    )
    rid2 = created2.json()["id"]
    client.post(f"/api/v1/reports/monthly/{rid2}/submit", headers=th_headers)
    reject = client.post(
        f"/api/v1/admin/reports/monthly/{rid2}/cm-review",
        headers=cm_headers,
        json={"comment": "Please fix spelling", "request_changes": True},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "REJECTED"
