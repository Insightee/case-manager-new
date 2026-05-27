"""Upload/download round-trips via shared object storage (local backend in tests)."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run
from app.storage.factory import reset_storage_backend_for_tests
from app.storage.local_backend import LocalStorageBackend
from app.storage.object_io import is_object_store_key, put_stored_bytes, read_stored_bytes
from app.tests.conftest import api_items

client = TestClient(app)

_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


@pytest.fixture(autouse=True)
def reset_storage():
    reset_storage_backend_for_tests()
    yield
    reset_storage_backend_for_tests()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_put_get_roundtrip_helpers():
    key, provider = put_stored_bytes(
        "test-objects",
        "sample",
        filename="note.txt",
        data=b"hello",
        content_type="text/plain",
    )
    assert provider == "local"
    assert is_object_store_key(key)
    assert read_stored_bytes(key) == b"hello"
    backend = LocalStorageBackend()
    backend.delete(key)


def test_ticket_attachment_upload_download():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/tickets",
        headers=headers,
        data={"subject": "Storage ticket", "body": "Attachment test", "category": "OTHER"},
        files={"files": ("proof.txt", io.BytesIO(b"ticket-file"), "text/plain")},
    )
    assert created.status_code in (200, 201), created.text
    ticket_id = created.json()["id"]
    detail = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    attachments = detail.json().get("attachments") or []
    assert attachments
    att_id = attachments[0]["id"]
    dl = client.get(f"/api/v1/tickets/attachments/{att_id}/download", headers=headers)
    assert dl.status_code == 200
    assert dl.content == b"ticket-file"

    from app.core.database import SessionLocal
    from app.models.ticket_attachment import TicketAttachment

    db = SessionLocal()
    try:
        row = db.get(TicketAttachment, att_id)
        assert row is not None
        assert is_object_store_key(row.file_path)
    finally:
        db.close()


def test_generic_attachment_upload_download():
    token = _login("casemanager@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    case_id = api_items(cases.json())[0]["id"]
    up = client.post(
        "/api/v1/attachments",
        headers=headers,
        data={
            "case_id": str(case_id),
            "entity_type": "iep",
            "visibility_status": "INTERNAL_ONLY",
        },
        files={"file": ("doc.txt", io.BytesIO(b"generic-attach"), "text/plain")},
    )
    assert up.status_code == 201, up.text
    att_id = up.json()["id"]
    dl = client.get(f"/api/v1/attachments/{att_id}/download", headers=headers)
    assert dl.status_code == 200
    assert dl.content == b"generic-attach"
