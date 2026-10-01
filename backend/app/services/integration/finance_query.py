"""Read-only finance aggregates for integration principals.

Admin receivables and ledger routes stay on human tokens. These reads are
scoped to granted cases and omit child names, notes, and addresses.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.models.case import Case
from app.models.client_billing import ClientInvoice
from app.models.ledger_billing import BillingLedger
from app.services.integration.access import IntegrationPrincipal, granted_case_ids, require_scope
from app.services.integration.errors import ForbiddenError, ValidationError
from app.services.integration.rate_limit import check_rate_limit

_NO_GRANTS = (
    "This integration client has no case grants. "
    "Grant every case, or pass case_ids. "
    "Empty totals would be an access gap, not an empty month."
)


def _billing_month(raw: str) -> str:
    value = (raw or "").strip()
    if len(value) != 7 or value[4] != "-":
        raise ValidationError("billing_month must be YYYY-MM.")
    year, month = value.split("-", 1)
    if not (year.isdigit() and month.isdigit() and 1 <= int(month) <= 12):
        raise ValidationError("billing_month must be YYYY-MM.")
    return value


def _require_finance_access(db: Session, principal: IntegrationPrincipal) -> set[int]:
    require_scope(principal, "finance:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    allowed = granted_case_ids(db, principal)
    if not principal.client.all_cases and not allowed:
        raise ForbiddenError(_NO_GRANTS)
    return allowed


def _money(value: Any) -> float:
    return round(float(value or 0), 2)


def _status_key(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _case_codes(db: Session, case_ids: set[int]) -> dict[int, str]:
    if not case_ids:
        return {}
    rows = db.execute(select(Case.id, Case.case_code).where(Case.id.in_(case_ids))).all()
    return {int(row[0]): row[1] for row in rows}


def receivables_summary(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    billing_month: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    ym = _billing_month(billing_month)
    allowed = _require_finance_access(db, principal)
    invoices = []
    if allowed:
        invoices = db.scalars(
            select(ClientInvoice).where(
                ClientInvoice.billing_month == ym,
                ClientInvoice.case_id.in_(allowed),
            )
        ).all()

    totals = {
        "billedInr": 0.0,
        "collectedInr": 0.0,
        "outstandingInr": 0.0,
        "invoiceCount": len(invoices),
    }
    by_case: dict[int, dict[str, Any]] = {}
    by_status: dict[str, dict[str, Any]] = {}
    for invoice in invoices:
        billed = _money(invoice.total_inr)
        collected = _money(invoice.amount_paid_inr)
        outstanding = round(billed - collected, 2)
        totals["billedInr"] += billed
        totals["collectedInr"] += collected
        totals["outstandingInr"] += outstanding
        bucket = by_case.setdefault(
            invoice.case_id,
            {
                "caseId": invoice.case_id,
                "billedInr": 0.0,
                "collectedInr": 0.0,
                "outstandingInr": 0.0,
                "invoiceCount": 0,
            },
        )
        bucket["billedInr"] = round(bucket["billedInr"] + billed, 2)
        bucket["collectedInr"] = round(bucket["collectedInr"] + collected, 2)
        bucket["outstandingInr"] = round(bucket["outstandingInr"] + outstanding, 2)
        bucket["invoiceCount"] += 1
        status = _status_key(invoice.status)
        status_bucket = by_status.setdefault(status, {"status": status, "invoiceCount": 0, "billedInr": 0.0})
        status_bucket["invoiceCount"] += 1
        status_bucket["billedInr"] = round(status_bucket["billedInr"] + billed, 2)

    for key in ("billedInr", "collectedInr", "outstandingInr"):
        totals[key] = round(totals[key], 2)
    codes = _case_codes(db, set(by_case))
    cases = []
    for case_id, row in sorted(by_case.items()):
        row["caseCode"] = codes.get(case_id)
        cases.append(row)

    payload = {
        "billingMonth": ym,
        "allCases": bool(principal.client.all_cases),
        "grantedCaseCount": len(allowed),
        "accessGap": False,
        "emptyBecause": None if invoices else "no_invoices_for_granted_cases",
        "totals": totals,
        "byStatus": list(by_status.values()),
        "byCase": cases,
    }
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.finance_receivables",
        entity_type="finance_receivables",
        entity_id=principal.client_id,
        new_value={"billing_month": ym, "granted_case_count": len(allowed), "invoice_count": len(invoices)},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload


def ledger_summary(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    billing_month: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    ym = _billing_month(billing_month)
    allowed = _require_finance_access(db, principal)
    grouped = []
    if allowed:
        grouped = db.execute(
            select(
                BillingLedger.billable_status,
                func.count(),
                func.coalesce(func.sum(BillingLedger.total_inr), 0),
                func.coalesce(func.sum(BillingLedger.payout_amount_inr), 0),
            )
            .where(BillingLedger.ledger_month == ym, BillingLedger.case_id.in_(allowed))
            .group_by(BillingLedger.billable_status)
        ).all()

    by_status = []
    entry_count = 0
    total_inr = 0.0
    payout_inr = 0.0
    for status, count, amount, payout in grouped:
        count_i = int(count or 0)
        amount_f = _money(amount)
        payout_f = _money(payout)
        entry_count += count_i
        total_inr += amount_f
        payout_inr += payout_f
        by_status.append(
            {
                "billableStatus": _status_key(status),
                "entryCount": count_i,
                "totalInr": amount_f,
                "payoutInr": payout_f,
            }
        )

    payload = {
        "billingMonth": ym,
        "allCases": bool(principal.client.all_cases),
        "grantedCaseCount": len(allowed),
        "accessGap": False,
        "emptyBecause": None if entry_count else "no_ledger_rows_for_granted_cases",
        "totals": {
            "entryCount": entry_count,
            "totalInr": round(total_inr, 2),
            "payoutInr": round(payout_inr, 2),
        },
        "byStatus": by_status,
    }
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.finance_ledger",
        entity_type="finance_ledger",
        entity_id=principal.client_id,
        new_value={"billing_month": ym, "granted_case_count": len(allowed), "entry_count": entry_count},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload
