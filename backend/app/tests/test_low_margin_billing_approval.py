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
        "client_billing_effective_from": "2026-06-01",
        "therapist_remuneration_effective_from": "2026-06-01",
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


def test_reassignment_low_margin_billing_stays_pending():
    approver_headers = login_headers(client, "superadmin@demo.com")
    admin_headers = login_headers(client, "admin@demo.com")
    case_id = api_first_case_id(client, approver_headers)

    with SessionLocal() as db:
        for pending in db.scalars(
            select(BillingApprovalRequest).where(
                BillingApprovalRequest.case_id == case_id,
                BillingApprovalRequest.status == BillingApprovalStatus.PENDING,
            )
        ).all():
            pending.status = BillingApprovalStatus.REJECTED
        db.commit()

    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare&approved_only=false",
        headers=approver_headers,
    )
    assert therapists.status_code == 200, therapists.text
    rows = therapists.json() if isinstance(therapists.json(), list) else therapists.json().get("items", [])
    ids = [row.get("therapist_user_id") or row.get("user_id") for row in rows]
    ids = [tid for tid in ids if tid]
    if len(set(ids)) < 2:
        return
    t1, t2 = list(dict.fromkeys(ids))[:2]

    current = client.get(f"/api/v1/cases/{case_id}/assignments", headers=approver_headers)
    assert current.status_code == 200
    active = next((row for row in current.json() if row.get("status") == "ACTIVE"), None)
    incoming = t2 if not active or active["therapist_user_id"] != t2 else t1

    assigned = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=admin_headers,
        json={
            "therapist_user_id": incoming,
            "start_date": "2026-08-17",
            "reason_for_change": "Incoming therapist needs a new rate card",
            "billing_update": _package_payload(client_amount=22000, therapist_amount=18000),
        },
    )
    assert assigned.status_code == 201, assigned.text
    body = assigned.json()
    assert body["billing_approval_status"] == "PENDING"
    assert body["projected_profit_inr"] == 4000

    case_after = client.get(f"/api/v1/cases/{case_id}", headers=approver_headers)
    assert case_after.status_code == 200
    assert case_after.json()["package_amount_inr"] != 22000
