"""Report image storage: local/R2 abstraction, access control, validation."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.report_image import ReportImage
from app.seed.demo_seed import run as seed_run
from app.storage.factory import get_storage_backend, reset_storage_backend_for_tests
from app.storage.local_backend import LocalStorageBackend
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


def _therapist_case_id(headers: dict) -> int:
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    items = api_items(cases.json())
    assert items
    return items[0]["id"]


def test_local_storage_put_get_roundtrip():
    backend = LocalStorageBackend()
    key = "insightcase/test/report-images/case_1/monthly/report_1/test.png"
    result = backend.put_bytes(key, _TINY_PNG, "image/png")
    assert result.provider == "local"
    assert result.key == key
    assert result.size_bytes == len(_TINY_PNG)
    assert backend.get_bytes(key) == _TINY_PNG
    assert backend.exists(key)
    backend.delete(key)
    assert not backend.exists(key)


def test_report_image_upload_stores_metadata():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = _therapist_case_id(headers)
    created = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": "Storage Meta 2099"},
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    up = client.post(
        f"/api/v1/reports/monthly/{rid}/images",
        headers=headers,
        files={"file": ("chart.png", io.BytesIO(_TINY_PNG), "image/png")},
    )
    assert up.status_code == 200, up.text
    img_id = up.json()["id"]

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(ReportImage, img_id)
        assert row is not None
        assert row.storage_provider == "local"
        assert row.storage_key
        assert row.mime_type == "image/png"
        assert row.size_bytes == len(_TINY_PNG)
        assert row.original_filename == "chart.png"
        assert row.file_path == row.storage_key
    finally:
        db.close()


def test_report_image_stream_content_type():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = _therapist_case_id(headers)
    created = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": "Stream CT 2099"},
    )
    rid = created.json()["id"]
    up = client.post(
        f"/api/v1/reports/monthly/{rid}/images",
        headers=headers,
        files={"file": ("x.png", io.BytesIO(_TINY_PNG), "image/png")},
    )
    img_id = up.json()["id"]
    img = client.get(f"/api/v1/reports/images/{img_id}", headers=headers)
    assert img.status_code == 200
    assert img.content == _TINY_PNG
    assert img.headers.get("content-type", "").startswith("image/png")


def test_reject_invalid_image_type():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = _therapist_case_id(headers)
    created = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": "Bad Type 2099"},
    )
    rid = created.json()["id"]
    bad = client.post(
        f"/api/v1/reports/monthly/{rid}/images",
        headers=headers,
        files={"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert bad.status_code == 400


def test_reject_oversized_image(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 100)
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = _therapist_case_id(headers)
    created = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": "Too Big 2099"},
    )
    rid = created.json()["id"]
    big = _TINY_PNG + b"x" * 200
    res = client.post(
        f"/api/v1/reports/monthly/{rid}/images",
        headers=headers,
        files={"file": ("big.png", io.BytesIO(big), "image/png")},
    )
    assert res.status_code == 400


def test_parent_cannot_access_draft_report_image():
    th_headers = {"Authorization": f"Bearer {_login('therapist@demo.com')}"}
    case_id = _therapist_case_id(th_headers)
    created = client.post(
        "/api/v1/reports/monthly",
        headers=th_headers,
        json={"case_id": case_id, "month": "Parent Deny 2099", "body_html": "<p>x</p>"},
    )
    rid = created.json()["id"]
    up = client.post(
        f"/api/v1/reports/monthly/{rid}/images",
        headers=th_headers,
        files={"file": ("x.png", io.BytesIO(_TINY_PNG), "image/png")},
    )
    img_id = up.json()["id"]
    parent_headers = {"Authorization": f"Bearer {_login('parent@demo.com')}"}
    denied = client.get(f"/api/v1/reports/images/{img_id}", headers=parent_headers)
    assert denied.status_code == 404


def test_parent_can_access_published_report_image():
    th_headers = {"Authorization": f"Bearer {_login('therapist@demo.com')}"}
    cm_headers = {"Authorization": f"Bearer {_login('casemanager@demo.com')}"}
    case_id = _therapist_case_id(th_headers)
    created = client.post(
        "/api/v1/reports/monthly",
        headers=th_headers,
        json={"case_id": case_id, "month": "Parent OK 2099", "body_html": "<p>Visible</p>"},
    )
    rid = created.json()["id"]
    up = client.post(
        f"/api/v1/reports/monthly/{rid}/images",
        headers=th_headers,
        files={"file": ("parent.png", io.BytesIO(_TINY_PNG), "image/png")},
    )
    assert up.status_code == 200, up.text
    img_id = up.json()["id"]
    client.post(f"/api/v1/reports/monthly/{rid}/submit", headers=th_headers)
    approve = client.post(
        f"/api/v1/reports/monthly/{rid}/approve",
        headers=cm_headers,
        json={"comment": "ok", "visibility_status": "APPROVED_FOR_PARENT"},
    )
    assert approve.status_code == 200, approve.text
    parent_headers = {"Authorization": f"Bearer {_login('parent@demo.com')}"}
    ok = client.get(f"/api/v1/reports/images/{img_id}", headers=parent_headers)
    assert ok.status_code == 200
    assert ok.content == _TINY_PNG


def test_r2_backend_put_get_mocked(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "r2")
    monkeypatch.setattr(settings, "r2_account_id", "acct")
    monkeypatch.setattr(settings, "r2_access_key_id", "key")
    monkeypatch.setattr(settings, "r2_secret_access_key", "secret")
    monkeypatch.setattr(settings, "r2_bucket_name", "bucket")
    monkeypatch.setattr(settings, "r2_endpoint_url", "https://acct.r2.cloudflarestorage.com")

    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = _TINY_PNG
    mock_client.get_object.return_value = {"Body": mock_body}

    with patch("app.storage.r2_backend.boto3.client", return_value=mock_client):
        reset_storage_backend_for_tests()
        backend = get_storage_backend()
        assert backend.provider == "r2"
        result = backend.put_bytes("insightcase/prod/report-images/case_1/monthly/1/x.png", _TINY_PNG, "image/png")
        assert result.provider == "r2"
        mock_client.put_object.assert_called_once()
        call_kw = mock_client.put_object.call_args.kwargs
        assert call_kw["Bucket"] == "bucket"
        assert call_kw["ContentType"] == "image/png"
        assert "ACL" not in call_kw
        data = backend.get_bytes("insightcase/prod/report-images/case_1/monthly/1/x.png")
        assert data == _TINY_PNG


def test_r2_factory_requires_credentials(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "r2")
    monkeypatch.setattr(settings, "r2_bucket_name", "")
    reset_storage_backend_for_tests()
    with pytest.raises(RuntimeError, match="STORAGE_PROVIDER=r2"):
        get_storage_backend()
