from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.billing_approval_request import BillingApprovalRequest, BillingApprovalStatus
from app.models.notification import Notification
from app.models.user import User
from app.tests.conftest import api_first_case_id, login_headers


client = TestClient(app)


def _package_payload(*, client_amount: float, therapist_amount: float) -> dict:
    return {
        "billing_type": "PACKAGE",
        "client_billing_mode": "PREPAID",
        "package_session_count": 10,
        "package_amount_inr": client_amount,
        "client_rate_per_session_inr": None,
        "compensation_mode": "PERCENTAGE",
        "pay_share_amount_inr": therapist_amount,
        "therapist_fixed_pay_inr": None,
    }


def test_hr_low_margin_change_waits_for_designated_approval():
    approver_headers = login_headers(client, "superadmin@demo.com")
    hr_headers = login_headers(client, "hr@demo.com")
    case_id = api_first_case_id(client, approver_headers)

    high_margin = client.patch(
        f"/api/v1/cases/{case_id}/billing",
        headers=approver_headers,
        json=_package_payload(client_amount=30000, therapist_amount=20000),
    )
    assert high_margin.status_code == 200, high_margin.text
    assert high_margin.json()["package_amount_inr"] == 30000

    with SessionLocal() as db:
        for pending in db.scalars(
            select(BillingApprovalRequest).where(
                BillingApprovalRequest.case_id == case_id,
                BillingApprovalRequest.status == BillingApprovalStatus.PENDING,
            )
        ).all():
            pending.status = BillingApprovalStatus.REJECTED
        db.commit()

    requested = client.patch(
        f"/api/v1/cases/{case_id}/billing",
        headers=hr_headers,
        json=_package_payload(client_amount=24000, therapist_amount=20000),
    )
    assert requested.status_code == 200, requested.text
    body = requested.json()
    assert body["billing_approval_status"] == "PENDING"
    assert body["projected_profit_inr"] == 4000
    assert body["package_amount_inr"] == 30000
    request_id = body["billing_approval_request_id"]

    with SessionLocal() as db:
        row = db.get(BillingApprovalRequest, request_id)
        assert row is not None
        assert row.requester.email == "hr@demo.com"
        assert row.applied_at is None
        approver = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        notification = db.scalars(
            select(Notification).where(
                Notification.user_id == approver.id,
                Notification.entity_type == "billing_approval_request",
                Notification.entity_id == request_id,
            )
        ).first()
        assert notification is not None

    detail = client.get(f"/api/v1/billing-approvals/{request_id}", headers=approver_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["canReview"] is True

    approved = client.post(
        f"/api/v1/billing-approvals/{request_id}/approve",
        headers=approver_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["appliedAt"] is not None

    case_after = client.get(f"/api/v1/cases/{case_id}", headers=approver_headers)
    assert case_after.status_code == 200
    assert case_after.json()["package_amount_inr"] == 24000

    with SessionLocal() as db:
        audit_actions = set(
            db.scalars(
                select(AuditEvent.action).where(
                    AuditEvent.entity_type == "billing_approval_request",
                    AuditEvent.entity_id == str(request_id),
                )
            ).all()
        )
        assert "request_low_margin_billing_approval" in audit_actions
        assert "approve_low_margin_billing" in audit_actions


def test_rejected_low_margin_change_keeps_current_billing():
    approver_headers = login_headers(client, "superadmin@demo.com")
    hr_headers = login_headers(client, "hr@demo.com")
    case_id = api_first_case_id(client, approver_headers)

    requested = client.patch(
        f"/api/v1/cases/{case_id}/billing",
        headers=hr_headers,
        json=_package_payload(client_amount=23000, therapist_amount=20000),
    )
    assert requested.status_code == 200, requested.text
    request_id = requested.json()["billing_approval_request_id"]

    rejected = client.post(
        f"/api/v1/billing-approvals/{request_id}/reject",
        headers=approver_headers,
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["appliedAt"] is None

    case_after = client.get(f"/api/v1/cases/{case_id}", headers=approver_headers)
    assert case_after.status_code == 200
    assert case_after.json()["package_amount_inr"] == 24000
