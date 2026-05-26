"""Case document upload size limit."""
from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case

client = TestClient(app)
ensure_sqlite_schema_patches()


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_case_document_rejects_oversized_upload():
    token = _login("superadmin@demo.com")
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case is not None
        case_id = case.id

    big = b"x" * (5 * 1024 * 1024 + 1)
    files = {"file": ("big.pdf", BytesIO(big), "application/pdf")}
    data = {
        "category": "OTHER",
        "title": "Too large",
        "source_type": "UPLOAD",
    }
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert r.status_code == 413
