from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _first_case_id(headers: dict) -> int:
    r = client.get("/api/v1/cases?page_size=1", headers=headers)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", data)
    assert items
    return int(items[0]["id"])


def _parent_case_id(headers: dict) -> int:
    r = client.get("/api/v1/parent/home", headers=headers)
    assert r.status_code == 200
    cases = r.json().get("cases") or []
    assert cases, "parent needs a linked case in seed"
    return int(cases[0]["id"])


def test_create_uploaded_document():
    headers = _login("therapist@demo.com")
    case_id = _first_case_id(headers)
    pdf = io.BytesIO(b"%PDF-1.4 test content")
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data={
            "category": "OBSERVATION_REPORT",
            "title": "Observation PDF",
            "source_type": "UPLOAD",
        },
        files={"file": ("obs.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "DRAFT"
    assert body["visibility"] == "INTERNAL_ONLY"
    assert body["current_version"]["source_type"] == "UPLOAD"


def test_create_google_link_document():
    headers = _login("casemanager@demo.com")
    case_id = _first_case_id(headers)
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        json={
            "category": "CLIENT_MONTHLY_REPORT",
            "title": "Monthly via Google",
            "source_type": "EXTERNAL_LINK",
            "external_url": "https://docs.google.com/document/d/abc123/edit",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["current_version"]["external_provider"] == "GOOGLE_DOCS"


def test_invalid_google_folder_rejected():
    headers = _login("casemanager@demo.com")
    case_id = _first_case_id(headers)
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        json={
            "category": "OTHER",
            "title": "Bad link",
            "source_type": "EXTERNAL_LINK",
            "external_url": "https://drive.google.com/drive/folders/abc123",
        },
    )
    assert r.status_code == 400


def test_parent_cannot_see_internal_document():
    cm_headers = _login("casemanager@demo.com")
    case_id = _first_case_id(cm_headers)
    create = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=cm_headers,
        json={
            "category": "OTHER",
            "title": "Internal only doc",
            "source_type": "EXTERNAL_LINK",
            "external_url": "https://docs.google.com/document/d/internal1/edit",
        },
    )
    assert create.status_code == 201
    doc_id = create.json()["id"]
    parent_headers = _login("parent@demo.com")
    list_r = client.get("/api/v1/parent/documents", headers=parent_headers)
    assert list_r.status_code == 200
    ids = {item["id"] for item in list_r.json().get("items", [])}
    assert doc_id not in ids


def test_supervisor_approve_and_parent_sees_published():
    parent_headers = _login("parent@demo.com")
    case_id = _parent_case_id(parent_headers)
    cm_headers = _login("casemanager@demo.com")
    create = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=cm_headers,
        json={
            "category": "MONTHLY_PROGRESS_REPORT",
            "title": "Progress report",
            "source_type": "EXTERNAL_LINK",
            "external_url": "https://docs.google.com/document/d/progress99/edit",
        },
    )
    assert create.status_code == 201
    doc_id = create.json()["id"]
    client.post(
        f"/api/v1/documents/{doc_id}/workflow/submit",
        headers=cm_headers,
        json={},
    )
    sup_headers = _login("supervisor@demo.com")
    client.post(
        f"/api/v1/documents/{doc_id}/workflow/approve",
        headers=sup_headers,
        json={"visibility": "CLIENT_VISIBLE_AFTER_APPROVAL"},
    )
    client.post(
        f"/api/v1/documents/{doc_id}/workflow/publish_client",
        headers=sup_headers,
        json={},
    )
    parent_headers = _login("parent@demo.com")
    list_r = client.get("/api/v1/parent/documents", headers=parent_headers)
    assert list_r.status_code == 200
    ids = {item["id"] for item in list_r.json().get("items", [])}
    assert doc_id in ids


def test_supervisor_request_changes():
    headers = _login("therapist@demo.com")
    case_id = _first_case_id(headers)
    create = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data={
            "category": "OBSERVATION_REPORT",
            "title": "Needs fixes",
            "source_type": "UPLOAD",
        },
        files={"file": ("o.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    doc_id = create.json()["id"]
    client.post(f"/api/v1/documents/{doc_id}/workflow/submit", headers=headers, json={})
    sup_headers = _login("supervisor@demo.com")
    r = client.post(
        f"/api/v1/documents/{doc_id}/workflow/request_changes",
        headers=sup_headers,
        json={"comment": "Add more detail"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "CHANGES_REQUESTED"


def test_comments_on_document():
    headers = _login("therapist@demo.com")
    case_id = _first_case_id(headers)
    create = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data={
            "category": "OTHER",
            "title": "Comment test",
            "source_type": "UPLOAD",
        },
        files={"file": ("c.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    doc_id = create.json()["id"]
    r = client.post(
        f"/api/v1/documents/{doc_id}/comments",
        headers=headers,
        json={"body": "Please review", "comment_type": "GENERAL"},
    )
    assert r.status_code == 201
    listed = client.get(f"/api/v1/documents/{doc_id}/comments", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) >= 1


def test_finance_denied_create():
    headers = _login("finance@demo.com")
    case_id = _first_case_id(_login("superadmin@demo.com"))
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        json={
            "category": "CLIENT_MONTHLY_REPORT",
            "title": "Finance attempt",
            "source_type": "EXTERNAL_LINK",
            "external_url": "https://docs.google.com/document/d/fin1/edit",
        },
    )
    assert r.status_code in (403, 404)


def test_hr_denied_create_clinical():
    headers = _login("hr@demo.com")
    case_id = _first_case_id(_login("superadmin@demo.com"))
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        json={
            "category": "IEP_PLAN",
            "title": "HR clinical",
            "source_type": "EXTERNAL_LINK",
            "external_url": "https://docs.google.com/document/d/hr1/edit",
        },
    )
    assert r.status_code in (403, 404)
