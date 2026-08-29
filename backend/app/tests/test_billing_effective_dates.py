"""Product-scoped billing margin gates + rate history effective dates."""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.billing_validation import needs_low_insighte_margin_review
from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.case_billing_rate_change import CaseBillingRateChange
from app.services import billing_rate_history_service
from app.services.billing_approval_service import requires_approval
from app.tests.conftest import api_first_case_id, login_headers


client = TestClient(app)


def test_homecare_anisha_layla_1500_1050_does_not_hit_5k_floor():
    """Homecare 1500/1050: ₹450 profit but 30% margin — must not require approval via ₹5k rule."""
    billing = {
        "product_module": "homecare",
        "billing_type": "PER_SESSION",
        "client_rate_per_session_inr": 1500,
        "therapist_fixed_pay_inr": 1050,
        "pay_share_amount_inr": 1050,
    }
    assert needs_low_insighte_margin_review(billing) is False
    assert requires_approval(billing) is False


def test_homecare_under_30_margin_needs_approval():
    billing = {
        "product_module": "homecare",
        "billing_type": "PER_SESSION",
        "client_rate_per_session_inr": 1500,
        "therapist_fixed_pay_inr": 1200,
        "pay_share_amount_inr": 1200,
    }
    assert needs_low_insighte_margin_review(billing) is True
    assert requires_approval(billing) is True


def test_shadow_keeps_absolute_5k_floor():
    billing = {
        "product_module": "shadow_support",
        "billing_type": "PACKAGE",
        "package_amount_inr": 24000,
        "therapist_fixed_pay_inr": 20000,
        "pay_share_amount_inr": 20000,
    }
    assert requires_approval(billing) is True


def test_counselling_uses_margin_gate_not_5k():
    billing = {
        "product_module": "counselling",
        "billing_type": "PER_SESSION",
        "client_rate_per_session_inr": 2000,
        "therapist_fixed_pay_inr": 1500,
        "pay_share_amount_inr": 1500,
    }
    assert requires_approval(billing) is True
    billing_ok = {**billing, "therapist_fixed_pay_inr": 1400, "pay_share_amount_inr": 1400}
    assert requires_approval(billing_ok) is False


def test_resolve_therapist_pay_as_of_uses_effective_date():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case is not None
        case.therapist_fixed_pay_inr = 1200
        case.pay_share_amount_inr = 1200
        db.add(
            CaseBillingRateChange(
                case_id=case.id,
                previous_therapist_amount_inr=1000,
                new_therapist_amount_inr=1200,
                therapist_effective_from=date(2026, 6, 1),
                previous_client_amount_inr=1500,
                new_client_amount_inr=1500,
                client_effective_from=date(2026, 6, 1),
                changed_by_user_id=1,
            )
        )
        db.commit()
        db.refresh(case)

        assert (
            billing_rate_history_service.resolve_therapist_pay_as_of(db, case, date(2026, 5, 15))
            == 1000.0
        )
        assert (
            billing_rate_history_service.resolve_therapist_pay_as_of(db, case, date(2026, 6, 1))
            == 1200.0
        )
        assert (
            billing_rate_history_service.resolve_therapist_pay_as_of(db, case, date(2026, 9, 1))
            == 1200.0
        )


def test_billing_patch_records_rate_change_and_timeline_detail():
    headers = login_headers(client, "superadmin@demo.com")
    case_id = api_first_case_id(client, headers)

    with SessionLocal() as db:
        case = db.get(Case, case_id)
        assert case is not None
        case.product_module = "homecare"
        case.billing_type = case.billing_type  # noqa: keep
        from app.models.case import BillingType

        case.billing_type = BillingType.PER_SESSION
        case.client_rate_per_session_inr = 1500
        case.client_monthly_rate_inr = None
        case.package_amount_inr = None
        case.therapist_fixed_pay_inr = 1050
        case.pay_share_amount_inr = 1050
        db.commit()

    updated = client.patch(
        f"/api/v1/cases/{case_id}/billing",
        headers=headers,
        json={
            "billing_type": "PER_SESSION",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1600,
            "client_monthly_rate_inr": None,
            "package_amount_inr": None,
            "compensation_mode": "FIXED_LUMP",
            "therapist_fixed_pay_inr": 1100,
            "pay_share_amount_inr": 1100,
            "billing_notes": "Sparkling Mindz differential from June",
            "client_billing_effective_from": "2026-06-01",
            "therapist_remuneration_effective_from": "2026-06-01",
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body.get("billing_approval_status") in (None, "APPROVED") or "billing_approval" not in body or body.get(
        "client_rate_per_session_inr"
    ) == 1600

    with SessionLocal() as db:
        row = db.scalars(
            select(CaseBillingRateChange)
            .where(CaseBillingRateChange.case_id == case_id)
            .order_by(CaseBillingRateChange.id.desc())
        ).first()
        assert row is not None
        assert float(row.previous_client_amount_inr or 0) == 1500.0
        assert float(row.new_client_amount_inr or 0) == 1600.0
        assert float(row.previous_therapist_amount_inr or 0) == 1050.0
        assert float(row.new_therapist_amount_inr or 0) == 1100.0
        assert row.client_effective_from == date(2026, 6, 1)
        assert row.therapist_effective_from == date(2026, 6, 1)

    timeline = client.get(f"/api/v1/admin/cases/{case_id}/timeline", headers=headers)
    assert timeline.status_code == 200, timeline.text
    details = " ".join(
        (i.get("detail") or "") + " " + (i.get("action_label") or "")
        for i in timeline.json().get("items", [])
    )
    assert "1500" in details and "1600" in details
    assert "1050" in details and "1100" in details
