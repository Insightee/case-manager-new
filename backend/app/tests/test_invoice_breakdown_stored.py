"""Invoice breakdown uses stored payout snapshots; submit rejects empty months."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.main import app
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine, InvoiceSessionLine
from app.seed.demo_seed import run as seed_run
from app.services import invoice_billing_service as billing

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _headers(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_seeded_invoices_have_persisted_session_lines():
    db = SessionLocal()
    try:
        invoices = db.scalars(select(Invoice).order_by(Invoice.id)).all()
        assert invoices, "Expected seeded therapist invoices"
        for inv in invoices:
            case_lines = db.scalar(
                select(func.count()).select_from(InvoiceCaseLine).where(InvoiceCaseLine.invoice_id == inv.id)
            )
            session_lines = db.scalar(
                select(func.count())
                .select_from(InvoiceSessionLine)
                .join(InvoiceCaseLine)
                .where(InvoiceCaseLine.invoice_id == inv.id)
            )
            assert case_lines > 0, f"Invoice {inv.month} missing case lines"
            assert session_lines > 0, f"Invoice {inv.month} missing session lines"
    finally:
        db.close()


def test_breakdown_amounts_match_invoice_list():
    headers = _headers("therapist@demo.com")
    listed = client.get("/api/v1/invoices", headers=headers)
    assert listed.status_code == 200
    for inv in listed.json():
        br = client.get(f"/api/v1/invoices/{inv['id']}/breakdown", headers=headers)
        assert br.status_code == 200, br.text
        body = br.json()
        assert body["net_amount_inr"] == pytest.approx(inv["amount_inr"], rel=0.01), inv["month"]
        assert body.get("from_preview") is not True, inv["month"]
        assert body.get("from_stored_header") is not True, inv["month"]


def test_paid_invoice_breakdown_shows_stored_sessions():
    headers = _headers("therapist@demo.com")
    listed = client.get("/api/v1/invoices", headers=headers).json()
    paid = next(i for i in listed if i["status"] == "PAID")
    br = client.get(f"/api/v1/invoices/{paid['id']}/breakdown", headers=headers).json()
    lines = sum(len(c.get("session_lines") or []) for c in br.get("cases") or [])
    assert lines > 0
    assert br["net_amount_inr"] == pytest.approx(paid["amount_inr"], rel=0.01)


def test_submit_rejects_zero_payout_month():
    headers = _headers("therapist@demo.com")
    submit = client.post(
        "/api/v1/invoices/submit",
        headers=headers,
        json={"month": "2026-03", "notes": "Should fail"},
    )
    assert submit.status_code == 400
    assert "billable payout" in submit.json().get("detail", "").lower()


def test_preview_has_billable_payout_helper():
    db = SessionLocal()
    try:
        from app.models.user import User

        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        empty = billing.build_month_preview(db, therapist.id, "2026-03")
        assert billing.preview_has_billable_payout(empty) is False
        may = billing.build_month_preview(db, therapist.id, "May 2026")
        assert billing.preview_has_billable_payout(may) is True
    finally:
        db.close()


def test_stored_header_fallback_for_legacy_invoice_without_lines():
    db = SessionLocal()
    try:
        from app.models.user import User

        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        inv = Invoice(
            therapist_user_id=therapist.id,
            month="Jan 2026",
            amount_inr=5000,
            subtotal_inr=5000,
            sessions_count=4,
            status=InvoiceStatus.PAID,
            paid_amount_inr=5000,
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        breakdown = billing.invoice_breakdown(db, inv.id)
        assert breakdown["net_amount_inr"] == 5000
        assert breakdown.get("from_stored_header") is True
        assert breakdown.get("cases")
        db.delete(inv)
        db.commit()
    finally:
        db.close()
