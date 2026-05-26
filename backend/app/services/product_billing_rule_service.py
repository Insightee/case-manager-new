from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger_billing import ProductBillingModel, ProductBillingRule


def list_rules(db: Session, *, active_only: bool = True, product_module: Optional[str] = None) -> list[dict]:
    stmt = select(ProductBillingRule).order_by(ProductBillingRule.product_name)
    if active_only:
        stmt = stmt.where(ProductBillingRule.active.is_(True))
    if product_module:
        stmt = stmt.where(ProductBillingRule.product_module == product_module)
    rows = db.scalars(stmt).all()
    return [_serialize(r) for r in rows]


def get_rule(db: Session, rule_id: int) -> ProductBillingRule | None:
    return db.get(ProductBillingRule, rule_id)


def create_rule(db: Session, data: dict) -> ProductBillingRule:
    rule = ProductBillingRule(
        product_name=data["product_name"],
        product_category=data["product_category"],
        product_module=data["product_module"],
        billing_model=ProductBillingModel(data["billing_model"]),
        default_rate_inr=data.get("default_rate_inr"),
        monthly_fee_inr=data.get("monthly_fee_inr"),
        package_sessions=data.get("package_sessions"),
        package_validity_days=data.get("package_validity_days"),
        gst_applicable=data.get("gst_applicable", True),
        gst_rate_percent=data.get("gst_rate_percent"),
        hsn_sac_code=data.get("hsn_sac_code"),
        payment_terms=data.get("payment_terms"),
        client_no_show_billable=data.get("client_no_show_billable", False),
        therapist_cancel_billable=data.get("therapist_cancel_billable", False),
        included_paid_leaves=data.get("included_paid_leaves"),
        unpaid_leave_deduction_method=data.get("unpaid_leave_deduction_method"),
        active=data.get("active", True),
        notes=data.get("notes"),
    )
    db.add(rule)
    db.flush()
    return rule


def update_rule(db: Session, rule: ProductBillingRule, data: dict) -> ProductBillingRule:
    for key, value in data.items():
        if value is None:
            continue
        if key == "billing_model":
            rule.billing_model = ProductBillingModel(value)
        else:
            setattr(rule, key, value)
    db.flush()
    return rule


def _serialize(r: ProductBillingRule) -> dict:
    return {
        "id": r.id,
        "productName": r.product_name,
        "productCategory": r.product_category,
        "productModule": r.product_module,
        "billingModel": r.billing_model.value,
        "defaultRateInr": float(r.default_rate_inr) if r.default_rate_inr is not None else None,
        "monthlyFeeInr": float(r.monthly_fee_inr) if r.monthly_fee_inr is not None else None,
        "packageSessions": r.package_sessions,
        "packageValidityDays": r.package_validity_days,
        "gstApplicable": r.gst_applicable,
        "gstRatePercent": float(r.gst_rate_percent) if r.gst_rate_percent is not None else None,
        "hsnSacCode": r.hsn_sac_code,
        "paymentTerms": r.payment_terms,
        "clientNoShowBillable": r.client_no_show_billable,
        "therapistCancelBillable": r.therapist_cancel_billable,
        "includedPaidLeaves": r.included_paid_leaves,
        "unpaidLeaveDeductionMethod": r.unpaid_leave_deduction_method,
        "active": r.active,
        "notes": r.notes,
    }
