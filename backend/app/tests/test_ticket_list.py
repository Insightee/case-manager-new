from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _case_id_for_code(token: str, case_code: str) -> int:
    r = client.get(f"/api/v1/cases?search={case_code}&page_size=5", headers=_headers(token))
    assert r.status_code == 200
    items = r.json().get("items") or []
    match = next((c for c in items if c.get("case_code") == case_code), None)
    assert match is not None, f"Case {case_code} not found"
    return match["id"]


def test_ticket_list_sorted_newest_first():
    admin = _login("superadmin@demo.com")
    first = client.post(
        "/api/v1/tickets",
        headers=_headers(admin),
        json={"subject": "Sort test older", "body": "First ticket", "category": "OTHER"},
    )
    second = client.post(
        "/api/v1/tickets",
        headers=_headers(admin),
        json={"subject": "Sort test newer", "body": "Second ticket", "category": "OTHER"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    listed = client.get(
        "/api/v1/tickets?search=Sort%20test&page_size=10",
        headers=_headers(admin),
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    ids = [t["id"] for t in items]
    assert second_id in ids
    assert first_id in ids
    assert ids.index(second_id) < ids.index(first_id)


def test_ticket_list_search_by_subject_and_therapist_name():
    admin = _login("superadmin@demo.com")
    therapist = _login("therapist@demo.com")
    case_id = _case_id_for_code(admin, "IC-2026-041")

    created = client.post(
        "/api/v1/tickets",
        headers=_headers(therapist),
        json={
            "case_id": case_id,
            "subject": "Unique search marker ticket",
            "body": "Linked to Aarav case",
            "category": "SERVICE",
        },
    )
    assert created.status_code == 201

    by_subject = client.get(
        "/api/v1/tickets?search=Unique%20search%20marker",
        headers=_headers(admin),
    )
    assert by_subject.status_code == 200
    assert any(t["subject"] == "Unique search marker ticket" for t in by_subject.json()["items"])

    by_client = client.get(
        "/api/v1/tickets?search=Aarav",
        headers=_headers(admin),
    )
    assert by_client.status_code == 200
    assert any(t.get("child_name") and "Aarav" in t["child_name"] for t in by_client.json()["items"])

    by_therapist = client.get(
        "/api/v1/tickets?search=Therapist%20Neha",
        headers=_headers(admin),
    )
    assert by_therapist.status_code == 200
    assert any(t.get("therapist_name") == "Therapist Neha" for t in by_therapist.json()["items"])


def test_ticket_list_pagination_and_status_filter():
    admin = _login("superadmin@demo.com")
    created = client.post(
        "/api/v1/tickets",
        headers=_headers(admin),
        json={"subject": "Pagination status open ticket", "body": "Open", "category": "OTHER"},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    page1 = client.get(
        "/api/v1/tickets?page=1&page_size=1&search=Pagination%20status%20open",
        headers=_headers(admin),
    )
    assert page1.status_code == 200
    body = page1.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["total"] >= 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == ticket_id

    open_only = client.get(
        "/api/v1/tickets?status=OPEN&search=Pagination%20status%20open",
        headers=_headers(admin),
    )
    assert open_only.status_code == 200
    assert all(t["status"] == "OPEN" for t in open_only.json()["items"])

    client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=_headers(admin),
        json={"body": "Closing note"},
    )
    resolved = client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=_headers(admin),
        json={"note": "Done"},
    )
    assert resolved.status_code == 200

    resolved_only = client.get(
        "/api/v1/tickets?status=RESOLVED&search=Pagination%20status%20open",
        headers=_headers(admin),
    )
    assert resolved_only.status_code == 200
    assert any(t["id"] == ticket_id for t in resolved_only.json()["items"])
