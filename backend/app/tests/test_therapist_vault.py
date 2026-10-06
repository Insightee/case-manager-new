"""Therapist profile vault document uploads and review."""
from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _pdf_bytes(label: str = "test") -> bytes:
    return f"%PDF-1.4\n%{label}\n".encode()


def test_therapist_upload_and_admin_approve_vault_document():
    therapist_headers = {"Authorization": f"Bearer {_login('therapist@demo.com')}"}
    admin_headers = {"Authorization": f"Bearer {_login('superadmin@demo.com')}"}

    overview = client.get("/api/v1/therapist/vault/documents", headers=therapist_headers)
    assert overview.status_code == 200, overview.text
    pan_row = next(r for r in overview.json()["fixed_documents"] if r["slot_key"] == "pan_card")
    assert pan_row["status"] == "MISSING"

    files = {"file": ("pan.pdf", BytesIO(_pdf_bytes("pan")), "application/pdf")}
    data = {"slot_key": "pan_card"}
    up = client.post("/api/v1/therapist/vault/documents/upload", headers=therapist_headers, data=data, files=files)
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]
    assert up.json()["status"] == "PENDING"

    me = client.get("/api/v1/auth/me", headers=therapist_headers).json()
    therapist_user_id = me["id"]

    admin_view = client.get(
        f"/api/v1/admin/therapist-profiles/{therapist_user_id}/vault/documents",
        headers=admin_headers,
    )
    assert admin_view.status_code == 200, admin_view.text

    approve = client.post(
        f"/api/v1/admin/therapist-profiles/{therapist_user_id}/vault/documents/{doc_id}/approve",
        headers=admin_headers,
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "APPROVED"

    files2 = {"file": ("pan2.pdf", BytesIO(_pdf_bytes("pan2")), "application/pdf")}
    blocked = client.post(
        "/api/v1/therapist/vault/documents/upload",
        headers=therapist_headers,
        data={"slot_key": "pan_card"},
        files=files2,
    )
    assert blocked.status_code == 400


def test_admin_reject_requires_reason():
    therapist_headers = {"Authorization": f"Bearer {_login('therapist@demo.com')}"}
    admin_headers = {"Authorization": f"Bearer {_login('superadmin@demo.com')}"}

    files = {"file": ("aadhaar.pdf", BytesIO(_pdf_bytes("aadhaar")), "application/pdf")}
    up = client.post(
        "/api/v1/therapist/vault/documents/upload",
        headers=therapist_headers,
        data={"slot_key": "aadhaar_card"},
        files=files,
    )
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]
    therapist_user_id = client.get("/api/v1/auth/me", headers=therapist_headers).json()["id"]

    reject_empty = client.post(
        f"/api/v1/admin/therapist-profiles/{therapist_user_id}/vault/documents/{doc_id}/reject",
        headers=admin_headers,
        json={},
    )
    assert reject_empty.status_code == 400

    reject = client.post(
        f"/api/v1/admin/therapist-profiles/{therapist_user_id}/vault/documents/{doc_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Image is blurry — please upload a clearer scan."},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "REJECTED"

    files2 = {"file": ("aadhaar-v2.pdf", BytesIO(_pdf_bytes("aadhaar2")), "application/pdf")}
    reup = client.post(
        "/api/v1/therapist/vault/documents/upload",
        headers=therapist_headers,
        data={"slot_key": "aadhaar_card"},
        files=files2,
    )
    assert reup.status_code == 201, reup.text
    assert reup.json()["status"] == "PENDING"
