"""Therapist pay share validation — flat lumpsum INR only."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.billing_validation import validate_case_billing
from app.main import app
from app.models.case import BillingType, Case, CompensationMode
from app.schemas.case import CaseUpdate
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _package_case(pay_share_amount_inr: float) -> Case:
    case = Case(
        id=99,
        case_code="T-SHARE",
        child_id=1,
        service_type="Shadow support",
        product_module="shadow_support",
    )
    case.billing_type = BillingType.PACKAGE
    case.package_session_count = 30
    case.package_amount_inr = 30000.0
    case.compensation_mode = CompensationMode.PERCENTAGE
    case.pay_share_amount_inr = pay_share_amount_inr
    return case


def test_case_update_schema_accepts_flat_share():
    CaseUpdate(pay_share_amount_inr=25000.0)
    CaseUpdate(pay_share_amount_inr=25050.5)
    CaseUpdate(therapist_fixed_pay_inr=25000.0)


def test_validate_case_billing_accepts_positive_share_within_client():
    validate_case_billing(_package_case(25000.0))
    validate_case_billing(_package_case(10000.0))
    # Share above client package amount is rejected.
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        validate_case_billing(_package_case(30001.0))
    assert excinfo.value.status_code == 400
    assert "cannot be more" in excinfo.value.detail.lower()


def test_validate_case_billing_rejects_missing_share():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        validate_case_billing(_package_case(0.0))
    assert excinfo.value.status_code == 400
    assert "therapist pay" in excinfo.value.detail.lower()


def _headers(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_patch_case_billing_coerces_to_fixed_lump():
    headers = _headers("superadmin@demo.com")
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    items = cases.json().get("items") or []
    assert items, "expected at least one seeded case"
    case_id = items[0]["id"]
    patch = client.patch(
        f"/api/v1/cases/{case_id}",
        headers=headers,
        json={
            "billing_type": "PACKAGE",
            "package_session_count": 30,
            "package_amount_inr": 30000.0,
            "compensation_mode": "PERCENTAGE",
            "pay_share_amount_inr": 25000.0,
            "client_billing_effective_from": "2026-06-01",
            "therapist_remuneration_effective_from": "2026-06-01",
        },
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["compensation_mode"] == "FIXED_LUMP"
    assert body["therapist_fixed_pay_inr"] == 25000.0
    assert body["pay_share_amount_inr"] == 25000.0
