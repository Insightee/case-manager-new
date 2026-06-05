"""Therapist pay share validation — no 70% cap; decimals allowed."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.billing_validation import validate_case_billing
from app.main import app
from app.models.case import BillingType, Case, CompensationMode
from app.schemas.case import CaseUpdate
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _package_case(pay_share_pct: float) -> Case:
    case = Case(
        id=99,
        case_code="T-SHARE",
        child_id=1,
        service_type="Shadow support",
        product_module="shadow_support",
    )
    case.billing_type = BillingType.PACKAGE
    case.package_session_count = 30
    case.package_amount_inr = 30000
    case.compensation_mode = CompensationMode.PERCENTAGE
    case.pay_share_pct = pay_share_pct
    return case


def test_case_update_schema_accepts_share_above_70_and_decimals():
    CaseUpdate(pay_share_pct=83)
    CaseUpdate(pay_share_pct=83.5)


def test_case_update_schema_rejects_share_above_100():
    with pytest.raises(ValidationError):
        CaseUpdate(pay_share_pct=100.1)


def test_validate_case_billing_accepts_share_above_70_and_decimals():
    validate_case_billing(_package_case(83))
    validate_case_billing(_package_case(83.5))


def _headers(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_patch_case_billing_accepts_high_decimal_share():
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
            "package_amount_inr": 30000,
            "compensation_mode": "PERCENTAGE",
            "pay_share_pct": 83.5,
        },
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["pay_share_pct"] == 83.5
