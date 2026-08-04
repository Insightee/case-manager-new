"""Package cycle drawdown + credit-forward rollover preview."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import BillingType, Case
from app.models.client_billing import CarePackage
from app.models.client_package_cycle import ClientPackageCycle, PackageBillingMode
from app.models.ledger_billing import ProductBillingModel, ProductBillingRule


_SHADOW_MODULES = frozenset({"shadow_support", "school_support", "school_services"})


def _is_shadow_or_retainer(case: Case, rule: ProductBillingRule | None) -> bool:
    module = (case.product_module or "").strip().lower()
    if module in _SHADOW_MODULES:
        return True
    if rule and rule.billing_model == ProductBillingModel.MONTHLY_FIXED:
        return True
    return case.billing_type == BillingType.MONTHLY_FIXED


def _billing_mode(case: Case) -> str:
    if case.billing_type == BillingType.PER_SESSION:
        return PackageBillingMode.HOMECARE_PER_SESSION.value
    return PackageBillingMode.PACKAGE.value


def get_active_cycle(db: Session, *, care_package_id: int) -> ClientPackageCycle | None:
    return db.scalars(
        select(ClientPackageCycle)
        .where(ClientPackageCycle.care_package_id == care_package_id)
        .order_by(ClientPackageCycle.cycle_index.desc())
    ).first()


def ensure_cycle_for_package(db: Session, pkg: CarePackage, case: Case) -> ClientPackageCycle:
    active = get_active_cycle(db, care_package_id=pkg.id)
    if active:
        return active
    rule = db.get(ProductBillingRule, pkg.product_billing_rule_id) if pkg.product_billing_rule_id else None
    shadow = _is_shadow_or_retainer(case, rule)
    remaining = max(0, pkg.total_sessions - pkg.used_sessions)
    cycle = ClientPackageCycle(
        care_package_id=pkg.id,
        case_id=pkg.case_id,
        cycle_index=1,
        billed_sessions=pkg.total_sessions,
        consumed_sessions=pkg.used_sessions,
        remaining_sessions=remaining,
        carry_forward_count=0,
        expires_on=pkg.validity_end,
        needs_review=shadow,
        billing_mode=_billing_mode(case),
        client_invoice_id=pkg.client_invoice_id,
    )
    db.add(cycle)
    db.flush()
    return cycle


def renewal_preview(db: Session, pkg: CarePackage, case: Case) -> dict:
    cycle = ensure_cycle_for_package(db, pkg, case)
    rule = db.get(ProductBillingRule, pkg.product_billing_rule_id) if pkg.product_billing_rule_id else None
    shadow = _is_shadow_or_retainer(case, rule)
    package_size = pkg.total_sessions
    remaining = max(0, cycle.remaining_sessions)
    consumed = cycle.consumed_sessions

    if shadow or cycle.needs_review:
        return {
            "carePackageId": pkg.id,
            "cycleIndex": cycle.cycle_index,
            "billedSessions": cycle.billed_sessions,
            "consumedSessions": consumed,
            "remainingSessions": remaining,
            "carryForwardCount": cycle.carry_forward_count,
            "expiresOn": cycle.expires_on.isoformat() if cycle.expires_on else None,
            "needsReview": True,
            "renewalBillableSessions": None,
            "nextCycleCapacity": package_size,
            "topUpRecommended": remaining <= max(1, package_size // 5),
            "billingMode": cycle.billing_mode,
            "message": "Finance review required before rollover credits apply.",
        }

    credit = remaining
    billable_delta = max(0, package_size - credit)
    next_expires = (cycle.expires_on or date.today()) + timedelta(days=30)
    return {
        "carePackageId": pkg.id,
        "cycleIndex": cycle.cycle_index,
        "billedSessions": cycle.billed_sessions,
        "consumedSessions": consumed,
        "remainingSessions": remaining,
        "carryForwardCount": credit,
        "expiresOn": cycle.expires_on.isoformat() if cycle.expires_on else None,
        "needsReview": False,
        "renewalBillableSessions": billable_delta,
        "nextCycleCapacity": package_size,
        "nextCyclePreview": f"Next cycle: {package_size}, less {credit} carried, {billable_delta} billable",
        "topUpRecommended": remaining <= max(1, package_size // 5),
        "billingMode": cycle.billing_mode,
        "message": None,
    }


def record_consumption(db: Session, *, care_package_id: int, sessions: int = 1) -> ClientPackageCycle | None:
    cycle = get_active_cycle(db, care_package_id=care_package_id)
    if not cycle:
        return None
    cycle.consumed_sessions = min(cycle.billed_sessions, cycle.consumed_sessions + sessions)
    cycle.remaining_sessions = max(0, cycle.billed_sessions - cycle.consumed_sessions)
    db.flush()
    return cycle


def advance_cycle(db: Session, pkg: CarePackage, case: Case) -> ClientPackageCycle:
    """Close current cycle and open next with credit-forward (standard PACKAGE only)."""
    current = ensure_cycle_for_package(db, pkg, case)
    rule = db.get(ProductBillingRule, pkg.product_billing_rule_id) if pkg.product_billing_rule_id else None
    shadow = _is_shadow_or_retainer(case, rule)
    package_size = pkg.total_sessions
    credit = max(0, current.remaining_sessions)

    if shadow:
        nxt = ClientPackageCycle(
            care_package_id=pkg.id,
            case_id=pkg.case_id,
            cycle_index=current.cycle_index + 1,
            billed_sessions=package_size,
            consumed_sessions=0,
            remaining_sessions=package_size,
            carry_forward_count=0,
            expires_on=(current.expires_on or date.today()) + timedelta(days=30),
            needs_review=True,
            billing_mode=current.billing_mode,
        )
        db.add(nxt)
        db.flush()
        return nxt

    # Credit-forward: unused credits expire after one cycle — do not carry beyond one renewal.
    billable_capacity = package_size
    nxt = ClientPackageCycle(
        care_package_id=pkg.id,
        case_id=pkg.case_id,
        cycle_index=current.cycle_index + 1,
        billed_sessions=billable_capacity,
        consumed_sessions=0,
        remaining_sessions=billable_capacity,
        carry_forward_count=credit,
        expires_on=(current.expires_on or date.today()) + timedelta(days=30),
        needs_review=False,
        billing_mode=PackageBillingMode.PACKAGE.value,
    )
    db.add(nxt)
    db.flush()
    return nxt
