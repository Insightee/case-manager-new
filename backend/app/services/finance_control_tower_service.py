"""Stage 1 Finance Control Tower — SELECT/aggregate only. Zero side effects."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.billing_month import default_billing_month, therapist_invoice_month_keys
from app.core.config import settings
from app.models.billing_step6 import BillingCalcException, BillingCalcExceptionCode
from app.models.case import BillingType, Case, CaseStatus
from app.models.child import Child
from app.models.client_billing import (
    BillingDispute,
    BillingDisputeStatus,
    ClientInvoice,
    ClientInvoiceStatus,
    ClientPayment,
    ClientPaymentStatus,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ledger_billing import BillableStatus, BillingLedger, BillingPeriodFlag, PeriodFlagKind
from app.models.user import User
from app.services import billing_composer_service, client_billing_service

Confidence = str  # RECONCILED | PARTIAL | ESTIMATED | INCOMPLETE

_CONFIDENCE_RANK = {
    "RECONCILED": 0,
    "PARTIAL": 1,
    "ESTIMATED": 2,
    "INCOMPLETE": 3,
}

_ASSIGNMENT_CODES = {
    BillingCalcExceptionCode.ASSIGNMENT_GAP.value,
    BillingCalcExceptionCode.ASSIGNMENT_OVERLAP.value,
    BillingCalcExceptionCode.ASSIGNMENT_PERIOD_OVERLAP.value,
    BillingCalcExceptionCode.RATE_PERIOD_GAP.value,
    BillingCalcExceptionCode.RATE_PERIOD_OVERLAP.value,
}
_LEAVE_CODES = {
    BillingCalcExceptionCode.UNKNOWN_LEAVE_TYPE.value,
    BillingCalcExceptionCode.MISSING_LEAVE_CREDIT_BALANCE.value,
}
_ADDON_CODES = {BillingCalcExceptionCode.MISSING_ADD_ON_RATE.value}
_PACKAGE_CODES = {BillingCalcExceptionCode.MISSING_PACKAGE_COUNT.value}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _cutover_complete() -> bool:
    return bool(settings.finance_cutover_complete)


def money_value(
    *,
    value: float | None,
    confidence: Confidence,
    confidence_reason: str,
    record_count: int,
    source_period: str,
    currency: str = "INR",
) -> dict[str, Any]:
    """Build MoneyValue. Never upgrade to RECONCILED for engine amounts pre-cutover."""
    conf = confidence
    if conf == "RECONCILED" and not _cutover_complete():
        conf = "PARTIAL"
        confidence_reason = (
            "Live financial cutover is pending — figures remain provisional (downgraded from reconciled)."
        )
    out: dict[str, Any] = {
        "currency": currency,
        "confidence": conf,
        "confidenceReason": confidence_reason,
        "recordCount": record_count,
        "sourcePeriod": source_period,
        "asOf": _now_iso(),
    }
    if value is not None:
        out["value"] = round(float(value), 2)
    return out


def count_card(
    *,
    count: int,
    confidence: Confidence,
    confidence_reason: str,
    source_period: str,
    impact: dict[str, Any] | None = None,
    oldest_age_days: int | None = None,
    drill_queue: str,
) -> dict[str, Any]:
    card = {
        "count": int(count),
        "confidence": confidence if not (confidence == "RECONCILED" and not _cutover_complete()) else "PARTIAL",
        "confidenceReason": confidence_reason,
        "sourcePeriod": source_period,
        "asOf": _now_iso(),
        "drillQueue": drill_queue,
    }
    if impact is not None:
        card["impact"] = impact
    if oldest_age_days is not None:
        card["oldestAgeDays"] = oldest_age_days
    return card


def lowest_confidence(*levels: Confidence) -> Confidence:
    present = [c for c in levels if c in _CONFIDENCE_RANK]
    if not present:
        return "ESTIMATED"
    return max(present, key=lambda c: _CONFIDENCE_RANK[c])


def _sum_ledger(
    db: Session,
    *,
    billing_month: str,
    statuses: list[BillableStatus] | None = None,
) -> tuple[float, int]:
    stmt = select(
        func.coalesce(func.sum(BillingLedger.total_inr), 0),
        func.count(BillingLedger.id),
    ).where(BillingLedger.ledger_month == billing_month)
    if statuses:
        stmt = stmt.where(BillingLedger.billable_status.in_(statuses))
    row = db.execute(stmt).one()
    return float(row[0] or 0), int(row[1] or 0)


def _exception_counts(db: Session, *, billing_month: str) -> dict[str, int]:
    rows = db.execute(
        select(BillingCalcException.code, func.count(BillingCalcException.id))
        .where(
            BillingCalcException.ledger_month == billing_month,
            BillingCalcException.resolved.is_(False),
        )
        .group_by(BillingCalcException.code)
    ).all()
    return {str(code): int(n) for code, n in rows}


def _oldest_exception_age_days(
    db: Session,
    *,
    billing_month: str,
    codes: set[str] | None = None,
) -> int | None:
    stmt = select(func.min(BillingCalcException.created_at)).where(
        BillingCalcException.ledger_month == billing_month,
        BillingCalcException.resolved.is_(False),
    )
    if codes:
        stmt = stmt.where(BillingCalcException.code.in_(list(codes)))
    created = db.scalar(stmt)
    if not created:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - created).days)


def _missing_package_cases(db: Session) -> list[Case]:
    return list(
        db.scalars(
            select(Case)
            .where(
                Case.status == CaseStatus.ACTIVE,
                Case.billing_type == BillingType.PACKAGE,
                or_(
                    Case.package_session_count.is_(None),
                    Case.package_session_count <= 0,
                ),
            )
            .options(selectinload(Case.child))
            .limit(500)
        ).all()
    )


def control_tower_summary(db: Session, *, billing_month: str | None = None) -> dict[str, Any]:
    ym = billing_composer_service.normalize_billing_month(billing_month or default_billing_month())
    month_keys = therapist_invoice_month_keys(ym)
    cutover = _cutover_complete()
    engine_available = bool(settings.enable_billing)
    ledger_writes = bool(settings.billing_ledger_writes)

    # Base counts (composer is read-only listing)
    ledger_ready = len(
        billing_composer_service.list_composer_cases(db, billing_month=ym, queue="ledger_ready", limit=500)
    )
    not_invoiced = len(
        billing_composer_service.list_composer_cases(
            db, billing_month=ym, queue="not_invoiced_this_month", limit=500
        )
    )
    open_disputes = int(
        db.scalar(
            select(func.count(BillingDispute.id)).where(
                BillingDispute.status.in_(
                    [BillingDisputeStatus.OPEN, BillingDisputeStatus.UNDER_REVIEW]
                )
            )
        )
        or 0
    )
    period_flags = int(
        db.scalar(
            select(func.count(BillingPeriodFlag.id)).where(
                BillingPeriodFlag.ledger_month == ym,
                BillingPeriodFlag.resolved.is_(False),
                BillingPeriodFlag.flag_kind == PeriodFlagKind.ACTIVE_NO_SESSIONS,
            )
        )
        or 0
    )
    pending_review = int(
        db.scalar(
            select(func.count(BillingLedger.id)).where(
                BillingLedger.ledger_month == ym,
                BillingLedger.billable_status == BillableStatus.PENDING_REVIEW,
            )
        )
        or 0
    )
    pending_finance = int(
        db.scalar(
            select(func.count(BillingLedger.id)).where(
                BillingLedger.ledger_month == ym,
                BillingLedger.billable_status == BillableStatus.PENDING_FINANCE,
            )
        )
        or 0
    )
    exc_by_code = _exception_counts(db, billing_month=ym)
    assignment_n = sum(exc_by_code.get(c, 0) for c in _ASSIGNMENT_CODES)
    leave_n = sum(exc_by_code.get(c, 0) for c in _LEAVE_CODES)
    addon_n = sum(exc_by_code.get(c, 0) for c in _ADDON_CODES)
    package_exc_n = sum(exc_by_code.get(c, 0) for c in _PACKAGE_CODES)
    missing_pkg_cases = _missing_package_cases(db)
    missing_pkg_n = max(len(missing_pkg_cases), package_exc_n)
    billing_exc_n = pending_review + pending_finance + sum(exc_by_code.values())

    payouts_held = int(
        db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.month.in_(month_keys),
                Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.QUERIED, InvoiceStatus.REJECTED]),
            )
        )
        or 0
    )
    payouts_in_review = int(
        db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.month.in_(month_keys),
                Invoice.status == InvoiceStatus.IN_REVIEW,
            )
        )
        or 0
    )
    payout_exc_n = payouts_held + payouts_in_review

    billable_amt, billable_n = _sum_ledger(
        db,
        billing_month=ym,
        statuses=[BillableStatus.BILLABLE, BillableStatus.INVOICED],
    )
    pending_amt, _ = _sum_ledger(
        db,
        billing_month=ym,
        statuses=[BillableStatus.PENDING_REVIEW, BillableStatus.PENDING_FINANCE],
    )

    receivables = client_billing_service.admin_receivables_summary(db, month=ym)
    recv_totals = receivables.get("totals") or {}
    outstanding_amt = float(recv_totals.get("outstandingInr") or 0)
    collected_amt = float(recv_totals.get("collectedInr") or 0)
    invoiced_amt = float(recv_totals.get("billedInr") or 0)
    invoiced_n = int(recv_totals.get("invoiceCount") or 0)
    therapist_payable = float(
        db.scalar(
            select(func.coalesce(func.sum(Invoice.amount_inr), 0)).where(
                Invoice.month.in_(month_keys),
                Invoice.status.in_(
                    [InvoiceStatus.DRAFT, InvoiceStatus.IN_REVIEW, InvoiceStatus.APPROVED]
                ),
            )
        )
        or 0
    )
    therapist_payable_n = int(
        db.scalar(
            select(func.count(Invoice.id)).where(
                Invoice.month.in_(month_keys),
                Invoice.status.in_(
                    [InvoiceStatus.DRAFT, InvoiceStatus.IN_REVIEW, InvoiceStatus.APPROVED]
                ),
            )
        )
        or 0
    )

    active_cases = int(
        db.scalar(select(func.count(Case.id)).where(Case.status == CaseStatus.ACTIVE)) or 0
    )
    cases_with_ledger = int(
        db.scalar(
            select(func.count(func.distinct(BillingLedger.case_id))).where(
                BillingLedger.ledger_month == ym
            )
        )
        or 0
    )
    cases_with_blocking = int(
        db.scalar(
            select(func.count(func.distinct(BillingCalcException.case_id))).where(
                BillingCalcException.ledger_month == ym,
                BillingCalcException.resolved.is_(False),
            )
        )
        or 0
    )

    # Confidence: engine ledger sums are PARTIAL pre-cutover; missing ledger → INCOMPLETE
    ledger_conf: Confidence = "PARTIAL" if billable_n > 0 else "INCOMPLETE"
    ledger_reason = (
        "Includes calculated ledger rows that have not completed production reconciliation"
        if billable_n > 0
        else "No persisted ledger rows for this billing month yet"
    )
    invoice_conf: Confidence = "PARTIAL" if invoiced_n > 0 else "INCOMPLETE"
    payout_conf: Confidence = "ESTIMATED"  # still partly log-gated invoice path

    page_confidence = lowest_confidence(
        ledger_conf,
        invoice_conf,
        payout_conf,
        "INCOMPLETE" if missing_pkg_n or assignment_n else "PARTIAL",
    )
    if not cutover and page_confidence == "RECONCILED":
        page_confidence = "PARTIAL"

    potential = money_value(
        value=billable_amt if billable_n else None,
        confidence=ledger_conf,
        confidence_reason=ledger_reason,
        record_count=billable_n,
        source_period=ym,
    )
    if billable_n == 0:
        potential.pop("value", None)

    action_queue = {
        "readyForBilling": count_card(
            count=ledger_ready,
            confidence="PARTIAL" if ledger_ready else "INCOMPLETE",
            confidence_reason="Composer ledger-ready queue from persisted ledger rows",
            source_period=ym,
            impact=money_value(
                value=billable_amt if ledger_ready else None,
                confidence=ledger_conf,
                confidence_reason=ledger_reason,
                record_count=ledger_ready,
                source_period=ym,
            )
            if ledger_ready and billable_n
            else None,
            drill_queue="ready_for_billing",
        ),
        "billingExceptions": count_card(
            count=billing_exc_n,
            confidence="PARTIAL" if billing_exc_n else "PARTIAL",
            confidence_reason="Holds + unresolved calculation exceptions",
            source_period=ym,
            impact=money_value(
                value=pending_amt if pending_amt else None,
                confidence="PARTIAL",
                confidence_reason="Sum of PENDING_REVIEW / PENDING_FINANCE ledger totals",
                record_count=pending_review + pending_finance,
                source_period=ym,
            )
            if pending_amt
            else None,
            oldest_age_days=_oldest_exception_age_days(db, billing_month=ym),
            drill_queue="billing_exceptions",
        ),
        "payoutExceptions": count_card(
            count=payout_exc_n,
            confidence="ESTIMATED",
            confidence_reason="Therapist invoices in draft/review/held for the month",
            source_period=ym,
            drill_queue="payout_exceptions",
        ),
        "missingPackageCounts": count_card(
            count=missing_pkg_n,
            confidence="INCOMPLETE",
            confidence_reason="Active PACKAGE cases missing package_session_count",
            source_period=ym,
            drill_queue="missing_package_counts",
        ),
        "assignmentIssues": count_card(
            count=assignment_n,
            confidence="INCOMPLETE" if assignment_n else "PARTIAL",
            confidence_reason="Persisted assignment / rate-period calculation exceptions",
            source_period=ym,
            oldest_age_days=_oldest_exception_age_days(db, billing_month=ym, codes=_ASSIGNMENT_CODES),
            drill_queue="assignment_issues",
        ),
        "leaveExceptions": count_card(
            count=leave_n,
            confidence="INCOMPLETE" if leave_n else "PARTIAL",
            confidence_reason="Leave credit / leave-type calculation exceptions",
            source_period=ym,
            oldest_age_days=_oldest_exception_age_days(db, billing_month=ym, codes=_LEAVE_CODES),
            drill_queue="leave_exceptions",
        ),
        "addOnExceptions": count_card(
            count=addon_n,
            confidence="INCOMPLETE" if addon_n else "PARTIAL",
            confidence_reason="Add-on sessions missing a configured client rate",
            source_period=ym,
            oldest_age_days=_oldest_exception_age_days(db, billing_month=ym, codes=_ADDON_CODES),
            drill_queue="addon_exceptions",
        ),
        "periodFlags": count_card(
            count=period_flags,
            confidence="PARTIAL",
            confidence_reason="Active cases with no sessions (period flags)",
            source_period=ym,
            drill_queue="period_flags",
        ),
        "uninvoicedEligible": count_card(
            count=not_invoiced,
            confidence="PARTIAL" if not_invoiced else "PARTIAL",
            confidence_reason="Composer not-invoiced queue for the billing month",
            source_period=ym,
            drill_queue="uninvoiced_eligible",
        ),
        "openDisputes": count_card(
            count=open_disputes,
            confidence="PARTIAL",
            confidence_reason="Open or under-review billing disputes",
            source_period=ym,
            drill_queue="open_disputes",
        ),
    }

    return {
        "billingMonth": ym,
        "asOf": _now_iso(),
        "engineAvailable": engine_available,
        "ledgerWritesEnabled": ledger_writes,
        "cutoverComplete": cutover,
        "readOnly": True,
        "pageConfidence": page_confidence,
        "pageConfidenceReason": (
            "Showing verified calculations from staging. Live financial cutover is pending, so figures remain provisional."
            if not cutover
            else "Cutover flag is set — still verify against source-of-truth financial records before treating as reconciled."
        ),
        "provisionalBanner": not cutover,
        "actionQueue": action_queue,
        "financeSummary": {
            "potentialBillable": potential,
            "invoiced": money_value(
                value=invoiced_amt if invoiced_n else None,
                confidence=invoice_conf,
                confidence_reason="Client invoice totals for the billing month",
                record_count=invoiced_n,
                source_period=ym,
            ),
            "collected": money_value(
                value=collected_amt if collected_amt else None,
                confidence="PARTIAL" if collected_amt else "INCOMPLETE",
                confidence_reason="Confirmed client payments linked to month invoices",
                record_count=invoiced_n,
                source_period=ym,
            ),
            "outstanding": money_value(
                value=outstanding_amt if outstanding_amt else None,
                confidence="ESTIMATED",
                confidence_reason="Outstanding without ageing buckets",
                record_count=invoiced_n,
                source_period=ym,
            ),
            "therapistPayable": money_value(
                value=therapist_payable if therapist_payable_n else None,
                confidence=payout_conf,
                confidence_reason="Therapist invoice amounts (eligibility still partly log-gated)",
                record_count=therapist_payable_n,
                source_period=ym,
            ),
            "exceptionImpact": money_value(
                value=pending_amt if pending_amt else None,
                confidence="PARTIAL",
                confidence_reason="Sum of ledger rows held in PENDING_REVIEW / PENDING_FINANCE",
                record_count=pending_review + pending_finance,
                source_period=ym,
            ),
        },
        "readinessFunnel": {
            "activeCases": active_cases,
            "inputsComplete": max(0, active_cases - missing_pkg_n),
            "ledgerCalculated": cases_with_ledger,
            "noBlockingException": max(0, cases_with_ledger - cases_with_blocking),
            "readyForBilling": ledger_ready,
        },
        "links": {
            "composerNotInvoiced": f"/admin/invoices/compose?billing_month={ym}&queue=not_invoiced_this_month",
            "composerLedgerReady": f"/admin/invoices/compose?billing_month={ym}&queue=ledger_ready",
            "clientPayments": "/admin/invoices?tab=payments",
            "disputes": "/admin/invoices?tab=disputes",
            "therapistPayouts": "/admin/therapist-payouts?sub=payouts",
            "controlTower": f"/admin/invoices?tab=overview&month={ym}",
        },
    }


def list_control_tower_exceptions(
    db: Session,
    *,
    billing_month: str | None = None,
    code: str | None = None,
    queue: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    ym = billing_composer_service.normalize_billing_month(
        billing_month or date.today().strftime("%Y-%m")
    )
    limit = max(1, min(int(limit or 100), 500))
    rows: list[dict[str, Any]] = []

    code_filter: set[str] | None = None
    if code:
        code_filter = {code}
    elif queue == "assignment_issues":
        code_filter = set(_ASSIGNMENT_CODES)
    elif queue == "leave_exceptions":
        code_filter = set(_LEAVE_CODES)
    elif queue == "addon_exceptions":
        code_filter = set(_ADDON_CODES)
    elif queue == "missing_package_counts":
        code_filter = set(_PACKAGE_CODES)

    if queue == "missing_package_counts":
        for c in _missing_package_cases(db)[:limit]:
            child_name = c.child.full_name if getattr(c, "child", None) else None
            rows.append(
                {
                    "exception": "MISSING_PACKAGE_COUNT",
                    "caseId": c.id,
                    "caseCode": c.case_code,
                    "clientName": child_name or "—",
                    "service": c.service_type,
                    "billingMonth": ym,
                    "financialImpact": None,
                    "owner": "Unassigned",
                    "ageDays": None,
                    "confidence": "INCOMPLETE",
                    "confidenceReason": "Package session count is missing",
                    "openHref": f"/admin/cases/{c.id}",
                }
            )

    if queue != "missing_package_counts" or code_filter:
        stmt = (
            select(BillingCalcException)
            .where(
                BillingCalcException.ledger_month == ym,
                BillingCalcException.resolved.is_(False),
            )
            .order_by(BillingCalcException.created_at.asc())
            .limit(limit)
        )
        if code_filter:
            stmt = stmt.where(BillingCalcException.code.in_(list(code_filter)))
        for ex in db.scalars(stmt).all():
            case = db.get(Case, ex.case_id)
            child_name = None
            if case:
                child = db.get(Child, case.child_id)
                child_name = child.full_name if child else None
            created = ex.created_at
            age = None
            if created:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age = max(0, (datetime.now(timezone.utc) - created).days)
            rows.append(
                {
                    "exception": ex.code,
                    "caseId": ex.case_id,
                    "caseCode": case.case_code if case else None,
                    "clientName": child_name or "—",
                    "service": case.service_type if case else None,
                    "billingMonth": ym,
                    "financialImpact": None,
                    "owner": "Unassigned",
                    "ageDays": age,
                    "confidence": "INCOMPLETE",
                    "confidenceReason": ex.message,
                    "openHref": f"/admin/cases/{ex.case_id}" if ex.case_id else None,
                    "sessionId": ex.session_id,
                }
            )

    if queue in (None, "period_flags", "billing_exceptions"):
        flags = db.scalars(
            select(BillingPeriodFlag)
            .where(
                BillingPeriodFlag.ledger_month == ym,
                BillingPeriodFlag.resolved.is_(False),
            )
            .limit(limit)
        ).all()
        for fl in flags:
            case = db.get(Case, fl.case_id)
            rows.append(
                {
                    "exception": fl.flag_kind.value if hasattr(fl.flag_kind, "value") else str(fl.flag_kind),
                    "caseId": fl.case_id,
                    "caseCode": case.case_code if case else None,
                    "clientName": "—",
                    "service": case.service_type if case else None,
                    "billingMonth": ym,
                    "financialImpact": None,
                    "owner": "Unassigned",
                    "ageDays": None,
                    "confidence": "PARTIAL",
                    "confidenceReason": fl.message,
                    "openHref": f"/admin/cases/{fl.case_id}",
                }
            )

    if queue in (None, "open_disputes", "billing_exceptions"):
        disputes = db.scalars(
            select(BillingDispute)
            .where(
                BillingDispute.status.in_(
                    [BillingDisputeStatus.OPEN, BillingDisputeStatus.UNDER_REVIEW]
                )
            )
            .options(selectinload(BillingDispute.invoice))
            .limit(limit)
        ).all()
        for d in disputes:
            inv = d.invoice
            rows.append(
                {
                    "exception": "DISPUTE",
                    "caseId": inv.case_id if inv else None,
                    "caseCode": None,
                    "clientName": "—",
                    "service": inv.service_type if inv else None,
                    "billingMonth": inv.billing_month if inv else ym,
                    "financialImpact": None,
                    "owner": "Unassigned",
                    "ageDays": None,
                    "confidence": "PARTIAL",
                    "confidenceReason": d.message or d.reason_code or "Open billing dispute",
                    "openHref": "/admin/invoices?tab=disputes",
                }
            )

    return {
        "billingMonth": ym,
        "asOf": _now_iso(),
        "confidence": "PARTIAL",
        "items": rows[:limit],
        "count": len(rows[:limit]),
    }


def list_billing_readiness(
    db: Session,
    *,
    billing_month: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    ym = billing_composer_service.normalize_billing_month(
        billing_month or date.today().strftime("%Y-%m")
    )
    limit = max(1, min(int(limit or 100), 500))
    cases = list(
        db.scalars(
            select(Case)
            .where(Case.status == CaseStatus.ACTIVE, Case.billing_type.is_not(None))
            .options(selectinload(Case.child))
            .order_by(Case.id)
            .limit(limit)
        ).all()
    )
    items = []
    for c in cases:
        ledger_rows = db.scalars(
            select(BillingLedger).where(
                BillingLedger.case_id == c.id,
                BillingLedger.ledger_month == ym,
            )
        ).all()
        expected = None
        ledger_status = "NONE"
        conf: Confidence = "INCOMPLETE"
        reason = "No persisted ledger rows for this case-month"
        if ledger_rows:
            expected = round(sum(float(r.total_inr or 0) for r in ledger_rows), 2)
            statuses = {r.billable_status for r in ledger_rows}
            if BillableStatus.PENDING_REVIEW in statuses or BillableStatus.PENDING_FINANCE in statuses:
                ledger_status = "HELD"
            elif BillableStatus.INVOICED in statuses:
                ledger_status = "INVOICED"
            elif BillableStatus.BILLABLE in statuses:
                ledger_status = "BILLABLE"
            else:
                ledger_status = "OTHER"
            conf = "PARTIAL"
            reason = "Sum of persisted ledger totals for the month"

        exc_n = int(
            db.scalar(
                select(func.count(BillingCalcException.id)).where(
                    BillingCalcException.case_id == c.id,
                    BillingCalcException.ledger_month == ym,
                    BillingCalcException.resolved.is_(False),
                )
            )
            or 0
        )
        inv = db.scalars(
            select(ClientInvoice)
            .where(ClientInvoice.case_id == c.id, ClientInvoice.billing_month == ym)
            .limit(1)
        ).first()
        inv_status = inv.status.value if inv and hasattr(inv.status, "value") else (inv.status if inv else "NONE")

        if c.billing_type == BillingType.PACKAGE and (
            not c.package_session_count or int(c.package_session_count) <= 0
        ):
            conf = "INCOMPLETE"
            reason = "Package count is missing"

        items.append(
            {
                "caseId": c.id,
                "caseCode": c.case_code,
                "clientName": c.child.full_name if c.child else "—",
                "service": c.service_type,
                "billingType": c.billing_type.value if c.billing_type else None,
                "expectedAmount": money_value(
                    value=expected,
                    confidence=conf,
                    confidence_reason=reason,
                    record_count=len(ledger_rows),
                    source_period=ym,
                )
                if expected is not None
                else {
                    "confidence": conf,
                    "confidenceReason": reason,
                    "recordCount": 0,
                    "sourcePeriod": ym,
                    "asOf": _now_iso(),
                    "currency": "INR",
                },
                "ledgerStatus": ledger_status,
                "exceptionStatus": "HAS_EXCEPTIONS" if exc_n else "CLEAR",
                "exceptionCount": exc_n,
                "invoiceStatus": inv_status,
                "confidence": conf,
                "viewHref": f"/admin/cases/{c.id}",
            }
        )

    return {
        "billingMonth": ym,
        "asOf": _now_iso(),
        "confidence": "PARTIAL",
        "items": items,
        "count": len(items),
    }


def list_payout_readiness(
    db: Session,
    *,
    billing_month: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    ym = billing_composer_service.normalize_billing_month(billing_month or default_billing_month())
    month_keys = therapist_invoice_month_keys(ym)
    limit = max(1, min(int(limit or 100), 500))
    invoices = list(
        db.scalars(
            select(Invoice)
            .where(Invoice.month.in_(month_keys))
            .order_by(Invoice.id.desc())
            .limit(limit)
        ).all()
    )
    # Group by therapist
    by_therapist: dict[int, list[Invoice]] = {}
    for inv in invoices:
        by_therapist.setdefault(inv.therapist_user_id, []).append(inv)

    items = []
    for tid, invs in by_therapist.items():
        user = db.get(User, tid)
        payable = round(sum(float(i.amount_inr or 0) for i in invs), 2)
        sessions = sum(int(i.sessions_count or 0) for i in invs)
        held = sum(
            1
            for i in invs
            if i.status in (InvoiceStatus.DRAFT, InvoiceStatus.QUERIED, InvoiceStatus.REJECTED)
        )
        case_ids: set[int] = set()
        for inv in invs:
            for cl in getattr(inv, "case_lines", []) or []:
                if getattr(cl, "case_id", None):
                    case_ids.add(cl.case_id)
        items.append(
            {
                "therapistUserId": tid,
                "therapistName": user.full_name if user else f"#{tid}",
                "cases": len(case_ids) or None,
                "payableUnits": sessions,
                "expectedPayout": money_value(
                    value=payable,
                    confidence="ESTIMATED",
                    confidence_reason="Therapist invoice amounts; eligibility still partly log-gated",
                    record_count=len(invs),
                    source_period=ym,
                ),
                "heldLines": held,
                "exceptionCount": held,
                "confidence": "ESTIMATED",
                "viewHref": f"/admin/therapist-payouts?sub=payouts&therapist_user_id={tid}",
            }
        )

    return {
        "billingMonth": ym,
        "asOf": _now_iso(),
        "confidence": "ESTIMATED",
        "items": items,
        "count": len(items),
    }
