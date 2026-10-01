"""G5: care_packages remaining SOT (Core OS Stabilisation PR3 / DEC-01)."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import today_ist
from app.models.case import BillingType, Case, ClientBillingMode
from app.models.client_billing import CarePackage, CarePackageStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services.package_effect_service import (
    apply_package_effect,
    session_package_invoice_locked,
)


def _ensure_package(db, case: Case, *, used: int = 0, total: int = 10) -> CarePackage:
    pkg = db.scalars(
        select(CarePackage).where(CarePackage.case_id == case.id).order_by(CarePackage.id.desc())
    ).first()
    parent = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
    parent_id = parent.id if parent else 1
    if pkg is None:
        pkg = CarePackage(
            case_id=case.id,
            parent_user_id=parent_id,
            name="G5 package",
            total_sessions=total,
            used_sessions=used,
            status=CarePackageStatus.ACTIVE,
        )
        db.add(pkg)
        db.flush()
    else:
        pkg.total_sessions = total
        pkg.used_sessions = used
        pkg.status = CarePackageStatus.ACTIVE
        db.flush()
    return pkg


def _timed_session(db, case: Case, therapist_id: int) -> TherapySession:
    now = datetime.now(timezone.utc)
    sess = TherapySession(
        case_id=case.id,
        therapist_user_id=therapist_id,
        scheduled_date=today_ist(),
        start_time=time(10, 0),
        end_time=time(11, 0),
        mode=SessionMode.HOME,
        status=SessionStatus.COMPLETED,
        actual_start_at=now - timedelta(hours=1),
        actual_end_at=now,
    )
    db.add(sess)
    db.flush()
    return sess


def test_consume_updates_used_sessions_even_without_times_flag_off(monkeypatch):
    import app.services.billing_ledger_service as bls

    monkeypatch.setattr(bls, "_ledger_writes_allowed", lambda: False)
    db = SessionLocal()
    try:
        case = db.scalars(select(Case).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist
        case.billing_type = BillingType.PACKAGE
        case.client_billing_mode = ClientBillingMode.PREPAID
        pkg = _ensure_package(db, case, used=2, total=10)
        before = pkg.used_sessions
        sess = _timed_session(db, case, therapist.id)
        result = apply_package_effect(db, case_id=case.id, session=sess, effect="consume")
        db.commit()
        db.refresh(pkg)
        assert result["applied"] is True
        assert pkg.used_sessions == before + 1
        # Idempotent
        again = apply_package_effect(db, case_id=case.id, session=sess, effect="consume")
        assert again["applied"] is False
        assert again["reason"] == "ALREADY_CONSUMED"
        db.refresh(pkg)
        assert pkg.used_sessions == before + 1
    finally:
        db.close()


def test_reverse_restores_used_sessions():
    db = SessionLocal()
    try:
        case = db.scalars(select(Case).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist
        case.billing_type = BillingType.PACKAGE
        pkg = _ensure_package(db, case, used=3, total=10)
        sess = _timed_session(db, case, therapist.id)
        apply_package_effect(db, case_id=case.id, session=sess, effect="consume")
        db.commit()
        db.refresh(pkg)
        mid = pkg.used_sessions
        rev = apply_package_effect(db, case_id=case.id, session=sess, effect="reverse")
        db.commit()
        db.refresh(pkg)
        assert rev["applied"] is True
        assert pkg.used_sessions == mid - 1
    finally:
        db.close()


def test_invoice_lock_helper_false_without_lines():
    db = SessionLocal()
    try:
        assert session_package_invoice_locked(db, session_id=99999999) is False
    finally:
        db.close()
