#!/usr/bin/env python3
"""Step 5 staging acceptance — eligibility holds (staging Postgres only, never production).

Creates STEP5-FIX-* fixtures and asserts acceptance checks 1–7.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select, text


def _staging_url() -> str:
    proc = subprocess.run(
        ["npx", "@railway/cli", "variables", "--environment", "staging", "--service", "Postgres", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    v = json.loads(proc.stdout)
    return "postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}".format(
        user=v["POSTGRES_USER"],
        pw=urllib.parse.quote_plus(v["POSTGRES_PASSWORD"]),
        host=v["RAILWAY_TCP_PROXY_DOMAIN"],
        port=v["RAILWAY_TCP_PROXY_PORT"],
        db=v["POSTGRES_DB"],
    )


def main() -> None:
    os.environ["DATABASE_URL"] = _staging_url()
    os.environ["APP_ENV"] = "staging"

    from app.core.database import SessionLocal
    from app.models.case import BillingType, Case, CaseStatus, CompensationMode
    from app.models.daily_log import DailyLog, LogApprovalStatus
    from app.models.ledger_billing import BillableStatus, BillingLedger, LedgerSourceType
    from app.models.session import Session as TherapySession
    from app.models.session import SessionMode, SessionStatus
    from app.services import billing_ledger_service, session_service

    db = SessionLocal()
    try:
        child_id = db.execute(text("SELECT id FROM children ORDER BY id LIMIT 1")).scalar()
        therapist_id = db.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
        assert child_id and therapist_id

        # Clean prior fixtures
        old_ids = [
            r[0]
            for r in db.execute(text("SELECT id FROM cases WHERE case_code LIKE 'STEP5-FIX-%'")).all()
        ]
        if old_ids:
            db.execute(
                text("DELETE FROM billing_ledger WHERE case_id = ANY(:ids)"),
                {"ids": old_ids},
            )
            db.execute(
                text(
                    "DELETE FROM daily_logs WHERE session_id IN "
                    "(SELECT id FROM sessions WHERE case_id = ANY(:ids))"
                ),
                {"ids": old_ids},
            )
            db.execute(text("DELETE FROM sessions WHERE case_id = ANY(:ids)"), {"ids": old_ids})
            db.execute(text("DELETE FROM cases WHERE id = ANY(:ids)"), {"ids": old_ids})
            db.commit()

        case = Case(
            case_code="STEP5-FIX-PER-SESSION",
            child_id=child_id,
            service_type="Homecare",
            product_module="homecare",
            status=CaseStatus.ACTIVE,
            billing_type=BillingType.PER_SESSION,
            client_rate_per_session_inr=1500.0,
            compensation_mode=CompensationMode.PERCENTAGE,
            pay_share_amount_inr=700.0,
            billing_address_same_as_service=True,
        )
        db.add(case)
        db.flush()

        # --- Check 1+6: orphan completed sessions → PENDING_REVIEW holds ---
        orphan_ids = []
        for day in (10, 11, 12):
            started = datetime(2026, 7, day, 4, 0, tzinfo=timezone.utc)
            sess = TherapySession(
                case_id=case.id,
                therapist_user_id=therapist_id,
                scheduled_date=date(2026, 7, day),
                start_time=time(10, 0),
                end_time=time(11, 0),
                mode=SessionMode.HOME,
                status=SessionStatus.IN_PROGRESS,
                actual_start_at=started,
            )
            db.add(sess)
            db.flush()
            ended = session_service.end_session(
                db, sess, end_at=started + timedelta(minutes=45)
            )
            orphan_ids.append(ended.id)
        db.commit()

        holds = db.scalars(
            select(BillingLedger).where(
                BillingLedger.session_id.in_(orphan_ids),
                BillingLedger.billable_status == BillableStatus.PENDING_REVIEW,
            )
        ).all()
        assert len(holds) == 3, f"expected 3 holds, got {len(holds)}"
        assert all(h.source_type == LedgerSourceType.SESSION for h in holds)
        hold_count = billing_ledger_service.count_log_holds(
            db, ledger_month="2026-07", case_id=case.id
        )
        assert hold_count >= 3
        print("CHECK1+6 PASS: orphan completions → PENDING_REVIEW holds, countable=", hold_count)

        # --- Check 2: approve flips same row, no DAILY_LOG duplicate ---
        target = db.get(TherapySession, orphan_ids[0])
        before = int(
            db.scalar(
                select(func.count(BillingLedger.id)).where(
                    BillingLedger.session_id == target.id
                )
            )
            or 0
        )
        hold_id = db.scalars(
            select(BillingLedger.id).where(BillingLedger.session_id == target.id)
        ).one()
        log = DailyLog(
            session_id=target.id,
            attendance_status="PRESENT",
            activities_done="Goals",
            observations="Steady",
            approval_status=LogApprovalStatus.APPROVED.value,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.flush()
        target.daily_log = log
        billing_ledger_service.upsert_from_daily_log_approved(db, log)
        db.commit()
        after = int(
            db.scalar(
                select(func.count(BillingLedger.id)).where(
                    BillingLedger.session_id == target.id
                )
            )
            or 0
        )
        row = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == target.id)
        ).one()
        assert before == after == 1
        assert row.id == hold_id
        assert row.billable_status == BillableStatus.BILLABLE
        assert row.source_type == LedgerSourceType.SESSION
        assert (
            db.scalar(
                select(func.count(BillingLedger.id)).where(
                    BillingLedger.session_id == target.id,
                    BillingLedger.source_type == LedgerSourceType.DAILY_LOG,
                )
            )
            or 0
        ) == 0
        print("CHECK2 PASS: approve flipped same SESSION row; count unchanged; no DAILY_LOG dupe")

        # --- Check 3: time_confirmation_required queue ---
        # Use "today" so update_actual_times edit window allows confirmation.
        today = date.today()
        started = datetime.now(timezone.utc) - timedelta(hours=2)
        conf = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist_id,
            scheduled_date=today,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=started,
            time_confirmation_required=True,
        )
        db.add(conf)
        db.flush()
        ended = session_service.end_session(
            db, conf, end_at=started + timedelta(minutes=50), auto_ended=True
        )
        db.commit()
        assert (
            db.scalar(
                select(func.count(BillingLedger.id)).where(
                    BillingLedger.session_id == ended.id
                )
            )
            or 0
        ) == 0
        queue = billing_ledger_service.list_needs_therapist_confirmation(db, case_id=case.id)
        assert any(q["sessionId"] == ended.id for q in queue)
        session_service.update_actual_times(
            db,
            ended,
            therapist_id,
            actual_start_at=started,
            actual_end_at=started + timedelta(minutes=45),
            edit_reason="Confirmed auto-end times for billing eligibility",
        )
        db.commit()
        conf_row = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == ended.id)
        ).one()
        assert conf_row.billable_status == BillableStatus.PENDING_REVIEW
        print("CHECK3 PASS: needs-confirmation queue then confirm → PENDING_REVIEW")

        # --- Check 4: reject → NON_BILLABLE ---
        rej_sess = db.get(TherapySession, orphan_ids[1])
        rej_hold = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == rej_sess.id)
        ).one()
        rej_log = DailyLog(
            session_id=rej_sess.id,
            attendance_status="PRESENT",
            activities_done="Notes",
            observations="x",
            approval_status=LogApprovalStatus.REJECTED.value,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(rej_log)
        db.flush()
        rej_sess.daily_log = rej_log
        billing_ledger_service.sync_session_status(db, rej_sess)
        db.commit()
        rej_row = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == rej_sess.id)
        ).one()
        assert rej_row.id == rej_hold.id
        assert rej_row.billable_status == BillableStatus.NON_BILLABLE
        print("CHECK4 PASS: rejected log → same row NON_BILLABLE")

        # --- Check 5: time edit in place (fresh session within 24h window) ---
        edit_started = datetime.now(timezone.utc) - timedelta(hours=1)
        edit_sess = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist_id,
            scheduled_date=today,
            start_time=time(14, 0),
            end_time=time(15, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=edit_started,
        )
        db.add(edit_sess)
        db.flush()
        edit_sess = session_service.end_session(
            db, edit_sess, end_at=edit_started + timedelta(minutes=45)
        )
        db.commit()
        edit_hold = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == edit_sess.id)
        ).one()
        session_service.update_actual_times(
            db,
            edit_sess,
            therapist_id,
            actual_start_at=edit_sess.actual_start_at,
            actual_end_at=edit_sess.actual_end_at + timedelta(minutes=5),
            edit_reason="Corrected late logout checkout time",
        )
        db.commit()
        edit_row = db.scalars(
            select(BillingLedger).where(BillingLedger.session_id == edit_sess.id)
        ).one()
        assert edit_row.id == edit_hold.id
        assert edit_row.source_type == LedgerSourceType.SESSION
        print("CHECK5 PASS: time edit updated same SESSION row")

        # --- Check 7: monthly amount unchanged (Step 2 calculator) ---
        from app.services.billing_ledger_service import (
            build_monthly_rate_periods,
            compute_monthly_fixed_amount,
        )

        monthly = Case(
            case_code="STEP5-FIX-MONTHLY-AMT",
            child_id=child_id,
            service_type="Shadow support",
            product_module="shadow_support",
            status=CaseStatus.ACTIVE,
            billing_type=BillingType.MONTHLY_FIXED,
            client_monthly_rate_inr=29000.0,
            compensation_mode=CompensationMode.FIXED_LUMP,
            pay_share_amount_inr=24000.0,
            billing_address_same_as_service=True,
            created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        periods = build_monthly_rate_periods(
            monthly, month_start=date(2026, 7, 1), month_end=date(2026, 7, 31)
        )
        amount, _, _ = compute_monthly_fixed_amount(
            periods, month_start=date(2026, 7, 1), month_end=date(2026, 7, 31)
        )
        assert amount == 29000.0
        print("CHECK7 PASS: MONTHLY_FIXED amount still ₹29,000 (no Step 2 change)")

        print("ALL STEP5 STAGING ACCEPTANCE CHECKS PASSED")
    finally:
        db.close()


if __name__ == "__main__":
    main()
