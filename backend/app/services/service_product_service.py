from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger_billing import ProductBillingModel, ProductBillingRule
from app.models.service_category import ServiceCategory
from app.models.service_product import ServiceProduct

_BILLING_MODEL_MAP = {
    "PER_SESSION": ProductBillingModel.POSTPAID_PER_SESSION,
    "POSTPAID_PER_SESSION": ProductBillingModel.POSTPAID_PER_SESSION,
    "PACKAGE": ProductBillingModel.PREPAID_PACKAGE,
    "PREPAID_PACKAGE": ProductBillingModel.PREPAID_PACKAGE,
    "MONTHLY": ProductBillingModel.MONTHLY_FIXED,
    "MONTHLY_FIXED": ProductBillingModel.MONTHLY_FIXED,
}


def product_to_dict(p: ServiceProduct) -> dict[str, Any]:
    return {
        "id": p.id,
        "service_category_id": p.service_category_id,
        "name": p.name,
        "billing_model": p.billing_model,
        "price_inr": float(p.price_inr) if p.price_inr is not None else None,
        "package_sessions": p.package_sessions,
        "discount_percent": float(p.discount_percent) if p.discount_percent is not None else None,
        "total_inr": float(p.total_inr) if p.total_inr is not None else None,
        "taxable": p.taxable,
        "gst_rate_percent": float(p.gst_rate_percent) if p.gst_rate_percent is not None else None,
        "gst_split": p.gst_split,
        "leave_policy": p.leave_policy,
        "active": p.active,
        "sort_order": p.sort_order,
        "product_billing_rule_id": p.product_billing_rule_id,
    }


def _sync_billing_rule(db: Session, product: ServiceProduct, category: ServiceCategory) -> None:
    model = _BILLING_MODEL_MAP.get((product.billing_model or "").upper(), ProductBillingModel.POSTPAID_PER_SESSION)
    rule = None
    if product.product_billing_rule_id:
        rule = db.get(ProductBillingRule, product.product_billing_rule_id)
    if not rule:
        rule = ProductBillingRule(
            product_name=product.name,
            product_category=category.label,
            product_module=category.id,
            billing_model=model,
            active=product.active,
        )
        db.add(rule)
        db.flush()
        product.product_billing_rule_id = rule.id
    rule.product_name = product.name
    rule.product_category = category.label
    rule.product_module = category.id
    rule.billing_model = model
    rule.default_rate_inr = product.price_inr
    rule.package_sessions = product.package_sessions
    rule.gst_applicable = product.taxable
    rule.gst_rate_percent = product.gst_rate_percent
    rule.active = product.active
    if model == ProductBillingModel.MONTHLY_FIXED:
        rule.monthly_fee_inr = product.total_inr or product.price_inr
    db.flush()


def list_products_for_category(db: Session, category_id: str) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ServiceProduct)
        .where(ServiceProduct.service_category_id == category_id)
        .order_by(ServiceProduct.sort_order, ServiceProduct.name)
    ).all()
    return [product_to_dict(r) for r in rows]


def create_product(db: Session, category_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    cat = db.get(ServiceCategory, category_id)
    if not cat:
        raise ValueError("Service category not found")
    product = ServiceProduct(
        service_category_id=category_id,
        name=payload["name"].strip(),
        billing_model=(payload.get("billing_model") or "PER_SESSION").upper(),
        price_inr=payload.get("price_inr"),
        package_sessions=payload.get("package_sessions"),
        discount_percent=payload.get("discount_percent"),
        total_inr=payload.get("total_inr"),
        taxable=payload.get("taxable", True),
        gst_rate_percent=payload.get("gst_rate_percent"),
        gst_split=payload.get("gst_split"),
        leave_policy=payload.get("leave_policy"),
        active=payload.get("active", True),
        sort_order=int(payload.get("sort_order") or 0),
    )
    db.add(product)
    db.flush()
    _sync_billing_rule(db, product, cat)
    return product_to_dict(product)


def update_product(db: Session, product_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    product = db.get(ServiceProduct, product_id)
    if not product:
        raise ValueError("Service product not found")
    cat = db.get(ServiceCategory, product.service_category_id)
    if not cat:
        raise ValueError("Service category not found")
    for field in (
        "name",
        "billing_model",
        "price_inr",
        "package_sessions",
        "discount_percent",
        "total_inr",
        "gst_rate_percent",
        "gst_split",
        "leave_policy",
        "sort_order",
    ):
        if field in payload and payload[field] is not None:
            val = payload[field]
            if field == "name":
                val = str(val).strip()
            if field == "billing_model":
                val = str(val).upper()
            setattr(product, field, val)
    if "taxable" in payload and payload["taxable"] is not None:
        product.taxable = bool(payload["taxable"])
    if "active" in payload and payload["active"] is not None:
        product.active = bool(payload["active"])
    db.flush()
    _sync_billing_rule(db, product, cat)
    return product_to_dict(product)


def delete_product(db: Session, product_id: int) -> None:
    product = db.get(ServiceProduct, product_id)
    if not product:
        raise ValueError("Service product not found")
    product.active = False
    if product.product_billing_rule_id:
        rule = db.get(ProductBillingRule, product.product_billing_rule_id)
        if rule:
            rule.active = False
    db.flush()
