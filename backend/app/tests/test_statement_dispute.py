"""Therapist statement disputes: mark sessions + comment, no amount edit.

Proves the bridge the finance statement queue will read (status + session_ids +
comment), and that a submitted invoice flips to the existing QUERIED status
without any amount being changed. Runs against the migrated schema (conftest
bootstraps ``alembic upgrade head``), so it also exercises the new table.
"""
import pytest

from app.core.database import SessionLocal
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.services import statement_dispute_service as svc


def _therapist_id(db) -> int:
    u = db.query(User).filter(User.email == "therapist@demo.com").first()
    assert u is not None, "seed therapist missing"
    return u.id


def test_dispute_no_invoice_records_sessions_and_comment():
    db = SessionLocal()
    try:
        tid = _therapist_id(db)
        d = svc.create_statement_dispute(
            db,
            therapist_user_id=tid,
            month="2099-01",
            comment="  Session on 3rd was cancelled but shows billed  ",
            session_ids=[11, 11, 22],
        )
        db.commit()
        assert d.status == "OPEN"
        assert d.disputed_session_ids == [11, 22]  # de-duped, order kept
        assert d.comment == "Session on 3rd was cancelled but shows billed"
        rows = svc.list_statement_disputes(db, month="2099-01")
        assert any(r.id == d.id for r in rows)
    finally:
        db.close()


def test_dispute_flips_submitted_invoice_to_queried_without_amount_edit():
    db = SessionLocal()
    try:
        tid = _therapist_id(db)
        inv = Invoice(
            therapist_user_id=tid, month="2099-02", amount_inr=1000, status=InvoiceStatus.IN_REVIEW
        )
        db.add(inv)
        db.flush()
        d = svc.create_statement_dispute(
            db,
            therapist_user_id=tid,
            month="2099-02",
            invoice_id=inv.id,
            comment="Please review case T-1 extra session",
            session_ids=[5],
        )
        db.commit()
        db.refresh(inv)
        assert inv.status == InvoiceStatus.QUERIED
        assert float(inv.amount_inr) == 1000.0  # NO amount edit
        assert d.invoice_id == inv.id
    finally:
        db.close()


def test_dispute_requires_comment():
    db = SessionLocal()
    try:
        tid = _therapist_id(db)
        with pytest.raises(ValueError):
            svc.create_statement_dispute(db, therapist_user_id=tid, month="2099-03", comment="   ")
    finally:
        db.close()


def test_finance_reads_all_therapist_reads_own():
    db = SessionLocal()
    try:
        tid = _therapist_id(db)
        svc.create_statement_dispute(
            db, therapist_user_id=tid, month="2099-04", comment="x", session_ids=[1]
        )
        db.commit()
        finance_view = svc.list_statement_disputes(db, month="2099-04")
        own_view = svc.list_statement_disputes(db, therapist_user_id=tid, month="2099-04")
        assert len(finance_view) >= 1
        assert all(r.therapist_user_id == tid for r in own_view)
    finally:
        db.close()
