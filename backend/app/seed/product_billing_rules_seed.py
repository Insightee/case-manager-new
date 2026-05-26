from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger_billing import ProductBillingModel, ProductBillingRule


def seed_product_billing_rules(db: Session) -> None:
    existing = db.scalar(select(ProductBillingRule.id).limit(1))
    if existing:
        return
    defaults = [
        ProductBillingRule(
            product_name="Shadow Support — Monthly",
            product_category="Shadow Support",
            product_module="shadow_support",
            billing_model=ProductBillingModel.MONTHLY_FIXED,
            monthly_fee_inr=45000,
            gst_applicable=True,
            gst_rate_percent=18,
            hsn_sac_code="999312",
            payment_terms="NET15",
            included_paid_leaves=2,
            active=True,
        ),
        ProductBillingRule(
            product_name="Homecare — Per Session",
            product_category="Homecare",
            product_module="homecare",
            billing_model=ProductBillingModel.POSTPAID_PER_SESSION,
            default_rate_inr=2500,
            gst_applicable=True,
            gst_rate_percent=18,
            hsn_sac_code="999312",
            payment_terms="NET7",
            client_no_show_billable=True,
            therapist_cancel_billable=False,
            active=True,
        ),
        ProductBillingRule(
            product_name="Homecare — 12 Session Package",
            product_category="Homecare",
            product_module="homecare",
            billing_model=ProductBillingModel.PREPAID_PACKAGE,
            default_rate_inr=2500,
            package_sessions=12,
            package_validity_days=90,
            gst_applicable=True,
            gst_rate_percent=18,
            hsn_sac_code="999312",
            active=True,
        ),
        ProductBillingRule(
            product_name="Shadow Support — Per Session",
            product_category="Shadow Support",
            product_module="shadow_support",
            billing_model=ProductBillingModel.POSTPAID_PER_SESSION,
            default_rate_inr=3000,
            gst_applicable=True,
            gst_rate_percent=18,
            active=True,
        ),
    ]
    for row in defaults:
        db.add(row)
    db.flush()
