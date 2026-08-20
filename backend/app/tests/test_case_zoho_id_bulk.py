"""Bulk case Zoho ID preview/apply and case PATCH."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.user import User
from app.seed.demo_seed import run as seed_run

ensure_sqlite_schema_patches()

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def _make_case(child_id: int, case_code: str) -> int:
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist is not None
        case = Case(
            case_code=case_code,
            child_id=child_id,
            service_type="Homecare",
            product_module="homecare",
            status=CaseStatus.ACTIVE,
        )
        db.add(case)
        db.flush()
        db.add(
            CaseAssignment(
                case_id=case.id,
                therapist_user_id=therapist.id,
                start_date=date.today(),
                status=CaseAssignmentStatus.ACTIVE,
            )
        )
        db.commit()
        return case.id
    finally:
        db.close()


def test_bulk_zoho_id_preview_skips_missing_and_does_not_write():
    suffix = uuid.uuid4().hex[:8]
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)

    fam = client.post(
        "/api/v1/admin/families",
        headers=ah,
        json={
            "parent_email": f"zoho-parent-{suffix}@demo.com",
            "parent_full_name": "Zoho Parent",
            "child": {"first_name": "Zoho", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]
    case_code = f"IC-ZOHO-{suffix}"
    case_id = _make_case(child_id, case_code)

    preview = client.post(
        "/api/v1/admin/cases/bulk-update-zoho-id",
        headers=ah,
        json={
            "apply": False,
            "rows": [
                {"case_code": case_code, "zoho_id": "INS-697"},
                {"case_code": case_code, "zoho_id": ""},
                {"case_code": "", "zoho_id": "CUS-00001"},
                {"case_code": "IC-MISSING-000", "zoho_id": "INS-001"},
            ],
        },
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["summary"]["will_update"] == 1
    assert body["summary"]["skipped"] == 2
    assert body["summary"]["failed"] == 1
    assert body["results"][0]["status"] == "will_update"

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None
        assert case.zoho_id is None
    finally:
        db.close()


def test_bulk_zoho_id_apply_and_unchanged():
    suffix = uuid.uuid4().hex[:8]
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)

    fam = client.post(
        "/api/v1/admin/families",
        headers=ah,
        json={
            "parent_email": f"zoho-apply-{suffix}@demo.com",
            "parent_full_name": "Zoho Apply Parent",
            "child": {"first_name": "Apply", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]
    case_code = f"IC-ZOHOA-{suffix}"
    case_id = _make_case(child_id, case_code)

    apply = client.post(
        "/api/v1/admin/cases/bulk-update-zoho-id",
        headers=ah,
        json={"apply": True, "rows": [{"case_code": case_code.lower(), "zoho_id": " CUS-00753 "}]},
    )
    assert apply.status_code == 200, apply.text
    assert apply.json()["summary"]["updated"] == 1

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None
        assert case.zoho_id == "CUS-00753"
    finally:
        db.close()

    again = client.post(
        "/api/v1/admin/cases/bulk-update-zoho-id",
        headers=ah,
        json={"apply": False, "rows": [{"case_code": case_code, "zoho_id": "CUS-00753"}]},
    )
    assert again.status_code == 200, again.text
    assert again.json()["summary"]["unchanged"] == 1


def test_patch_case_zoho_id():
    suffix = uuid.uuid4().hex[:8]
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    fam = client.post(
        "/api/v1/admin/families",
        headers=ah,
        json={
            "parent_email": f"zoho-patch-{suffix}@demo.com",
            "parent_full_name": "Zoho Patch Parent",
            "child": {"first_name": "Patch", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    case_id = _make_case(fam.json()["childId"], f"IC-ZOHOP-{suffix}")

    res = client.patch(f"/api/v1/cases/{case_id}", headers=ah, json={"zoho_id": "INS-455 A"})
    assert res.status_code == 200, res.text
    assert res.json()["zoho_id"] == "INS-455 A"
