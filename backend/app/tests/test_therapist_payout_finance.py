"""Therapist payout finance queue, resolve path, Monday brief — Loop 2."""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.case import Case
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine, InvoiceSessionLine, SessionLineSource, SessionLineType
from app.models.user import User
from app.models.therapist_statement_dispute import TherapistStatementDispute
from app.seed.demo_seed import run as seed_run
from app.services import statement_dispute_service, therapist_payout_queue_service
from app.services.therapist_payout_queue_service import _compute_statement_balances

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _therapist_id(db) -> int:
    u = db.query(User).filter(User.email == "therapist@demo.com").first()
    assert u is not None
    return u.id


def _invoice_with_session_line(db, *, amount: float = 1000.0, session_amount: float = 300.0, session_id: int = 9001):
    tid = _therapist_id(db)
    case = db.scalar(select(Case).limit(1))
    assert case is not None
    inv = Invoice(
        therapist_user_id=tid,
        month="2099-06",
        amount_inr=amount,
        subtotal_inr=amount,
        status=InvoiceStatus.IN_REVIEW,
        sessions_count=1,
    )
    db.add(inv)
    db.flush()
    cl = InvoiceCaseLine(
        invoice_id=inv.id,
        case_id=case.id,
        case_code=case.case_code or f"C-{case.id}",
        billing_type="PER_SESSION",
        included_sessions=1,
        therapist_share_inr=session_amount,
    )
    db.add(cl)
    db.flush()
    sl = InvoiceSessionLine(
        invoice_case_line_id=cl.id,
        session_id=session_id,
        session_date=date(2099, 6, 15),
        line_type=SessionLineType.PER_SESSION,
        amount_inr=session_amount,
        source=SessionLineSource.LOG,
        included=True,
    )
    db.add(sl)
    db.flush()
    return inv, session_id, session_amount


def test_compute_statement_balances_one_line_hold():
    balances = _compute_statement_balances(
        net_inr=1000.0,
        disputed_session_ids=[9001],
        session_map={9001: 300.0},
    )
    assert balances["contestedInr"] == 300.0
    assert balances["payableNowInr"] == 700.0
    assert balances["needsReview"] is False


def test_compute_statement_balances_unreconciled_id_holds():
    balances = _compute_statement_balances(
        net_inr=1000.0,
        disputed_session_ids=[9999],
        session_map={9001: 300.0},
    )
    assert balances["needsReview"] is True
    assert balances["payableNowInr"] is None


def test_resolve_statement_dispute_restores_status_and_audit():
    seed_run()
    db = SessionLocal()
    try:
        inv, session_id, _ = _invoice_with_session_line(db)
        d = statement_dispute_service.create_statement_dispute(
            db,
            therapist_user_id=inv.therapist_user_id,
            month=inv.month,
            invoice_id=inv.id,
            comment="Session billed incorrectly",
            session_ids=[session_id],
        )
        db.commit()
        db.refresh(inv)
        assert inv.status == InvoiceStatus.QUERIED
        assert d.prior_invoice_status == "IN_REVIEW"

        finance_h = _login("finance@demo.com")
        r = client.post(
            f"/api/v1/admin/therapist-payouts/statement-disputes/{d.id}/resolve",
            headers=finance_h,
            json={"status": "RESOLVED", "resolution": "Valid dispute — session removed via amend path"},
        )
        assert r.status_code == 200, r.text
        db.expire_all()
        inv2 = db.get(Invoice, inv.id)
        d2 = db.get(TherapistStatementDispute, d.id)
        assert inv2.status == InvoiceStatus.IN_REVIEW
        assert d2.status == "RESOLVED"
        assert d2.admin_resolution

        audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_type == "statement_dispute",
                AuditEvent.entity_id == d.id,
                AuditEvent.action == "resolve_statement_dispute",
            )
        )
        assert audit is not None
    finally:
        db.close()


def test_payout_queue_payable_now_split():
    seed_run()
    db = SessionLocal()
    try:
        inv, session_id, session_amount = _invoice_with_session_line(db)
        statement_dispute_service.create_statement_dispute(
            db,
            therapist_user_id=inv.therapist_user_id,
            month=inv.month,
            invoice_id=inv.id,
            comment="Dispute one session",
            session_ids=[session_id],
        )
        db.commit()

        finance_h = _login("finance@demo.com")
        q = client.get("/api/v1/admin/therapist-payouts/queue?month=2099-06", headers=finance_h)
        assert q.status_code == 200, q.text
        body = q.json()
        row = next(s for s in body["statements"] if s["invoiceId"] == inv.id)
        assert row["status"] == "QUERIED"
        assert row["contestedInr"] == session_amount
        # Queue payable-now uses settlement ladder net (gross from case lines), not legacy amount_inr.
        expected_net = round(float(session_amount) * 0.9, 2)  # 10% default TDS on gross 300
        assert row["payableNowInr"] == max(0.0, round(expected_net - session_amount, 2))
        assert row["needsReview"] is True  # QUERIED statements are blocked until resolved
    finally:
        db.close()


def test_rbac_blocks_parent_and_therapist():
    seed_run()
    parent_h = _login("parent@demo.com")
    therapist_h = _login("therapist@demo.com")
    finance_h = _login("finance@demo.com")

    for headers in (parent_h, therapist_h):
        assert client.get("/api/v1/admin/therapist-payouts/queue", headers=headers).status_code == 403
        assert client.get("/api/v1/admin/finance-overview/monday-brief", headers=headers).status_code == 403
        assert (
            client.post(
                "/api/v1/admin/therapist-payouts/statement-disputes/1/resolve",
                headers=headers,
                json={"status": "RESOLVED", "resolution": "nope"},
            ).status_code
            == 403
        )

    assert client.get("/api/v1/admin/therapist-payouts/queue", headers=finance_h).status_code == 200
    assert client.get("/api/v1/admin/finance-overview/monday-brief", headers=finance_h).status_code == 200


def test_monday_brief_matches_source_endpoints():
    db = SessionLocal()
    try:
        from app.seed.finance_walkthrough_fixture import _cleanup_walkthrough_cases

        _cleanup_walkthrough_cases(db)
    finally:
        db.close()
    seed_run()
    finance_h = _login("finance@demo.com")
    brief = client.get("/api/v1/admin/finance-overview/monday-brief", headers=finance_h).json()
    recv = client.get("/api/v1/admin/client-billing/receivables", headers=finance_h).json()
    ym = brief["billingMonth"]
    queue = client.get(f"/api/v1/admin/therapist-payouts/queue?month={ym}", headers=finance_h).json()

    assert brief["moneyIn"]["collectibleOutstandingInr"] == recv["totals"]["outstandingInr"]
    assert brief["moneyOut"]["totalPayableInr"] == queue["totals"]["totalPayableNowInr"]
    assert brief["moneyOut"]["statementsPendingApproval"] == queue["totals"]["pendingCount"]
