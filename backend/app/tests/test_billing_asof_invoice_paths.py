"""Invoice/payout paths must resolve therapist pay as-of service date, not live case only."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.case import BillingType, Case
from app.models.case_billing_rate_change import CaseBillingRateChange
from app.models.invoice_line import SessionLineType
from app.services import finance_payout_preview_service as payout
from app.services import invoice_billing_service as billing


def test_invoice_session_line_uses_therapist_rate_as_of_session_date():
    """Mid-month hike: sessions before effective date keep old pay; after use new."""
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case is not None
        for old in db.scalars(
            select(CaseBillingRateChange).where(CaseBillingRateChange.case_id == case.id)
        ).all():
            db.delete(old)
        case.product_module = "homecare"
        case.service_type = "homecare"
        case.billing_type = BillingType.PER_SESSION
        case.client_rate_per_session_inr = 1500
        case.therapist_fixed_pay_inr = 1200
        case.pay_share_amount_inr = 1200
        db.add(
            CaseBillingRateChange(
                case_id=case.id,
                previous_therapist_amount_inr=1000,
                new_therapist_amount_inr=1200,
                therapist_effective_from=date(2026, 6, 15),
                previous_client_amount_inr=1500,
                new_client_amount_inr=1500,
                client_effective_from=date(2026, 6, 1),
                changed_by_user_id=1,
            )
        )
        db.commit()

        early = billing.compute_session_line_amount(
            case, SessionLineType.PER_SESSION, db=db, as_of=date(2026, 6, 10)
        )
        late = billing.compute_session_line_amount(
            case, SessionLineType.PER_SESSION, db=db, as_of=date(2026, 6, 20)
        )
        assert early == 1000.0
        assert late == 1200.0

        may = billing.compute_session_line_amount(
            case, SessionLineType.PER_SESSION, db=db, as_of=date(2026, 5, 31)
        )
        assert may == 1000.0


def test_predicted_subtotal_respects_month_end_as_of():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case is not None
        for old in db.scalars(
            select(CaseBillingRateChange).where(CaseBillingRateChange.case_id == case.id)
        ).all():
            db.delete(old)
        case.product_module = "homecare"
        case.service_type = "homecare"
        case.billing_type = BillingType.PER_SESSION
        case.package_session_count = None
        case.therapist_fixed_pay_inr = 1200
        case.pay_share_amount_inr = 1200
        db.add(
            CaseBillingRateChange(
                case_id=case.id,
                previous_therapist_amount_inr=900,
                new_therapist_amount_inr=1200,
                therapist_effective_from=date(2026, 6, 1),
                changed_by_user_id=1,
            )
        )
        db.commit()

        may_total = payout.predicted_subtotal_inr(
            case, approved_sessions=4, db=db, as_of=date(2026, 5, 31)
        )
        june_total = payout.predicted_subtotal_inr(
            case, approved_sessions=4, db=db, as_of=date(2026, 6, 30)
        )
        assert may_total == 3600.0
        assert june_total == 4800.0
