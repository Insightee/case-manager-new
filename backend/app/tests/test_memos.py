from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _auth_headers(email: str = "superadmin@demo.com"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_memo_recipients_list():
    # Admin can view list
    r = client.get("/api/v1/memos/recipients", headers=_auth_headers("superadmin@demo.com"))
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    # Ensure no parent users are in list
    for rec in data:
        assert "PARENT" not in rec["roles"]

    # Therapist cannot view recipients list (403 Forbidden)
    r = client.get("/api/v1/memos/recipients", headers=_auth_headers("therapist@demo.com"))
    assert r.status_code == 403


def test_create_and_process_memo():
    # 1. Fetch a recipient user (Therapist)
    r = client.get("/api/v1/memos/recipients", headers=_auth_headers("superadmin@demo.com"))
    recipients = r.json()
    therapist_id = next(u["id"] for u in recipients if "THERAPIST" in u["roles"])

    # 2. Issue a memo
    payload = {
        "category": "Performance",
        "priority": "High",
        "recipient_type": "Therapist",
        "recipient_ids": [therapist_id],
        "subject": "Late daily logging concern",
        "details": "We noticed you have been submitting your session logs past the 24-hour SLA window.",
        "reply_required": True,
        "acknowledgement_only": False,
        "due_date": "2026-06-30"
    }
    r = client.post("/api/v1/memos", json=payload, headers=_auth_headers("superadmin@demo.com"))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "success"

    # 3. Check stats
    r = client.get("/api/v1/memos/stats", headers=_auth_headers("superadmin@demo.com"))
    assert r.status_code == 200
    assert r.json()["pending_reply"] >= 1

    # 4. List memos as recipient (Therapist)
    r = client.get("/api/v1/memos", headers=_auth_headers("therapist@demo.com"))
    assert r.status_code == 200
    memos = r.json()
    assert len(memos) >= 1
    memo = next(m for m in memos if m["subject"] == "Late daily logging concern")
    memo_id = memo["id"]
    assert memo["status"] == "PENDING_REPLY"

    # 5. Get details as recipient (This should auto-mark it as viewed)
    r = client.get(f"/api/v1/memos/{memo_id}", headers=_auth_headers("therapist@demo.com"))
    assert r.status_code == 200
    detail = r.json()
    assert detail["viewed_at"] is not None

    # 6. Recipient submits a reply (Moves status to UNDER_REVIEW)
    reply_payload = {"body": "My apologies, I had network connectivity issues. I will ensure it is within 24h going forward."}
    r = client.post(f"/api/v1/memos/{memo_id}/messages", json=reply_payload, headers=_auth_headers("therapist@demo.com"))
    assert r.status_code == 201

    # Verify status changed to UNDER_REVIEW
    r = client.get(f"/api/v1/memos/{memo_id}", headers=_auth_headers("superadmin@demo.com"))
    assert r.json()["status"] == "UNDER_REVIEW"

    # 7. Admin requests clarification (Moves status back to PENDING_REPLY)
    clarify_payload = {"body": "Please provide more details on when the connectivity issues occurred."}
    r = client.post(f"/api/v1/memos/{memo_id}/messages", json=clarify_payload, headers=_auth_headers("superadmin@demo.com"))
    assert r.status_code == 201

    r = client.get(f"/api/v1/memos/{memo_id}", headers=_auth_headers("superadmin@demo.com"))
    assert r.json()["status"] == "PENDING_REPLY"

    # 8. Close memo
    r = client.post(f"/api/v1/memos/{memo_id}/close", headers=_auth_headers("superadmin@demo.com"))
    assert r.status_code == 200

    r = client.get(f"/api/v1/memos/{memo_id}", headers=_auth_headers("superadmin@demo.com"))
    assert r.json()["status"] == "CLOSED"

    # 9. Reopen memo
    r = client.post(f"/api/v1/memos/{memo_id}/reopen", headers=_auth_headers("superadmin@demo.com"))
    assert r.status_code == 200

    r = client.get(f"/api/v1/memos/{memo_id}", headers=_auth_headers("superadmin@demo.com"))
    assert r.json()["status"] == "PENDING_REPLY"  # Since reply is required


def test_acknowledgement_memo():
    # 1. Fetch therapist
    r = client.get("/api/v1/memos/recipients", headers=_auth_headers("superadmin@demo.com"))
    recipients = r.json()
    therapist_id = next(u["id"] for u in recipients if "THERAPIST" in u["roles"])

    # 2. Create acknowledgement memo
    payload = {
        "category": "Compliance",
        "priority": "Low",
        "recipient_type": "Therapist",
        "recipient_ids": [therapist_id],
        "subject": "New safety procedures policy",
        "details": "Please read and acknowledge the updated safety procedures document linked.",
        "reply_required": False,
        "acknowledgement_only": True,
    }
    r = client.post("/api/v1/memos", json=payload, headers=_auth_headers("superadmin@demo.com"))
    assert r.status_code == 201

    # 3. Find created memo
    r = client.get("/api/v1/memos", headers=_auth_headers("therapist@demo.com"))
    memos = r.json()
    memo = next(m for m in memos if m["subject"] == "New safety procedures policy")
    memo_id = memo["id"]

    # 4. Acknowledge memo (should auto-close)
    r = client.post(f"/api/v1/memos/{memo_id}/acknowledge", headers=_auth_headers("therapist@demo.com"))
    assert r.status_code == 200

    r = client.get(f"/api/v1/memos/{memo_id}", headers=_auth_headers("therapist@demo.com"))
    detail = r.json()
    assert detail["acknowledged_at"] is not None
    assert detail["status"] == "CLOSED"


def test_export_memos():
    r = client.get("/api/v1/memos/export", headers=_auth_headers("superadmin@demo.com"))
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "Memo ID,Recipient Name" in r.text
