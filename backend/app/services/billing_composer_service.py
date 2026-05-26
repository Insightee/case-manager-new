"""Billing composer: case queues and preview for finance invoice workflow."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.client_billing import (
    BillingDispute,
    BillingDisputeStatus,
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceStatus,
    ClientInvoiceType,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine, InvoiceSessionLine
from app.models.ledger_billing import BillableStatus, BillingLedger, LedgerSourceType, ProductBillingRule
from app.models.parent import ParentGuardian
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services import billing_ledger_service, notification_service, product_billing_rule_service
from app.services.client_billing_service import _invoice_is_overdue, _parents_for_case

DEFAULT_PAYMENT_POLICY = """Payment is due on or before the due date mentioned in this invoice.

For bank transfers, please upload the payment screenshot or transaction reference after payment.

Invoices may include session charges, package fees, approved leave adjustments, discounts, taxes, and other agreed charges.

Any invoice concern must be raised within 3 working days.

Insighte will verify submitted payments before marking the invoice as paid."""

COMPOSER_QUEUES = (
    "all",
    "not_invoiced_this_month",
    "not_invoiced_last_30_days",
    "new_clients",
    "ledger_ready",
    "therapist_submitted",
    "therapist_pending",
    "disputed",
    "overdue",
    "draft",
)


def normalize_billing_month(billing_month: str) -> str:
    raw = (billing_month or "").strip()
    if len(raw) == 7 and raw[4] == "-":
        return raw
    try:
        parsed = datetime.strptime(raw, "%b %Y")
        return parsed.strftime("%Y-%m")
    except ValueError:
        pass
    try:
        parsed = datetime.strptime(raw, "%B %Y")
        return parsed.strftime("%Y-%m")
    except ValueError:
        pass
    return date.today().strftime("%Y-%m")


def _month_bounds(ym: str) -> tuple[date, date]:
    year_s, month_s = ym.split("-")[:2]
    y, m = int(year_s), int(month_s)
    last = monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last)


def _parent_guardian_for_case(db: Session, case: Case) -> ParentGuardian | None:
    return db.scalars(
        select(ParentGuardian)
        .join(ParentGuardian.children)
        .where(Child.id == case.child_id)
        .limit(1)
    ).first()


def _parent_name_for_case(db: Session, case: Case) -> str:
    pg = _parent_guardian_for_case(db, case)
    if not pg:
        return ""
    user = db.get(User, pg.user_id)
    return user.full_name if user and user.full_name else ""


def _parent_email_for_case(db: Session, case: Case) -> str:
    pg = _parent_guardian_for_case(db, case)
    if not pg:
        return ""
    user = db.get(User, pg.user_id)
    return user.email if user and user.email else ""


def _therapists_for_case(db: Session, case_id: int) -> list[dict]:
    rows = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.desc())
    ).all()
    out = []
    for a in rows:
        u = db.get(User, a.therapist_user_id)
        out.append(
            {
                "userId": a.therapist_user_id,
                "name": u.full_name if u and u.full_name else f"Therapist {a.therapist_user_id}",
            }
        )
    return out


def _case_has_invoice_for_month(db: Session, case_id: int, ym: str) -> bool:
    inv = db.scalar(
        select(ClientInvoice.id)
        .where(
            ClientInvoice.case_id == case_id,
            ClientInvoice.billing_month == ym,
            ClientInvoice.status.notin_([ClientInvoiceStatus.CANCELLED, ClientInvoiceStatus.VOID]),
        )
        .limit(1)
    )
    return inv is not None


def _case_invoice_count(db: Session, case_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ClientInvoice.id)).where(
                ClientInvoice.case_id == case_id,
                ClientInvoice.status.notin_([ClientInvoiceStatus.CANCELLED, ClientInvoiceStatus.VOID]),
            )
        )
        or 0
    )


def _sessions_completed_in_month(db: Session, case_id: int, ym: str) -> int:
    year_s, month_s = ym.split("-")[:2]
    return int(
        db.scalar(
            select(func.count(TherapySession.id)).where(
                TherapySession.case_id == case_id,
                extract("year", TherapySession.scheduled_date) == int(year_s),
                extract("month", TherapySession.scheduled_date) == int(month_s),
                TherapySession.status == SessionStatus.COMPLETED,
            )
        )
        or 0
    )


def _leaves_in_month(db: Session, case_id: int, ym: str) -> int:
    return int(
        db.scalar(
            select(func.count(BillingLedger.id)).where(
                BillingLedger.case_id == case_id,
                BillingLedger.ledger_month == ym,
                BillingLedger.source_type == LedgerSourceType.LEAVE,
            )
        )
        or 0
    )


def _ledger_ready_count(db: Session, case_id: int, ym: str) -> int:
    return int(
        db.scalar(
            select(func.count(BillingLedger.id)).where(
                BillingLedger.case_id == case_id,
                BillingLedger.ledger_month == ym,
                BillingLedger.billable_status == BillableStatus.BILLABLE,
                BillingLedger.client_invoice_id.is_(None),
            )
        )
        or 0
    )


def _therapist_submitted_for_case_month(db: Session, case_id: int, ym: str) -> bool:
    """Therapist invoice in review/approved/paid with case line for this case and month."""
    row = db.scalar(
        select(Invoice.id)
        .join(InvoiceCaseLine, InvoiceCaseLine.invoice_id == Invoice.id)
        .where(
            InvoiceCaseLine.case_id == case_id,
            Invoice.month == ym,
            Invoice.status.in_(
                [InvoiceStatus.IN_REVIEW, InvoiceStatus.APPROVED, InvoiceStatus.PAID]
            ),
        )
        .limit(1)
    )
    return row is not None


def _therapist_pending_for_case_month(db: Session, case_id: int, ym: str) -> bool:
    has_activity = (
        _sessions_completed_in_month(db, case_id, ym) > 0
        or _ledger_ready_count(db, case_id, ym) > 0
        or db.scalar(
            select(func.count(BillingLedger.id)).where(
                BillingLedger.case_id == case_id,
                BillingLedger.ledger_month == ym,
            )
        )
        > 0
    )
    if not has_activity:
        return False
    return not _therapist_submitted_for_case_month(db, case_id, ym)


def _case_has_open_dispute(db: Session, case_id: int) -> bool:
    row = db.scalar(
        select(BillingDispute.id)
        .join(ClientInvoice, BillingDispute.client_invoice_id == ClientInvoice.id)
        .where(
            ClientInvoice.case_id == case_id,
            BillingDispute.status.in_([BillingDisputeStatus.OPEN, BillingDisputeStatus.UNDER_REVIEW]),
        )
        .limit(1)
    )
    return row is not None


def _case_has_overdue_invoice(db: Session, case_id: int) -> bool:
    invoices = db.scalars(select(ClientInvoice).where(ClientInvoice.case_id == case_id)).all()
    for inv in invoices:
        balance = float(inv.total_inr) - float(inv.amount_paid_inr or 0)
        if _invoice_is_overdue(inv, balance):
            return True
    return False


def _case_has_draft_invoice(db: Session, case_id: int, ym: str) -> bool:
    row = db.scalar(
        select(ClientInvoice.id).where(
            ClientInvoice.case_id == case_id,
            ClientInvoice.billing_month == ym,
            ClientInvoice.status == ClientInvoiceStatus.DRAFT,
        )
    )
    return row is not None


def _build_case_card(db: Session, case: Case, ym: str) -> dict:
    rule = None
    if case.product_billing_rule_id:
        rule = product_billing_rule_service.get_rule(db, case.product_billing_rule_id)
    last_inv = db.scalar(
        select(ClientInvoice)
        .where(ClientInvoice.case_id == case.id)
        .order_by(ClientInvoice.created_at.desc())
        .limit(1)
    )
    badges: list[str] = []
    if _case_invoice_count(db, case.id) == 0:
        badges.append("new_client")
    if not _case_has_invoice_for_month(db, case.id, ym):
        badges.append("not_invoiced")
    if _ledger_ready_count(db, case.id, ym) > 0:
        badges.append("ledger_ready")
    if _therapist_submitted_for_case_month(db, case.id, ym):
        badges.append("therapist_submitted")
    if _therapist_pending_for_case_month(db, case.id, ym):
        badges.append("therapist_pending")
    if _case_has_open_dispute(db, case.id):
        badges.append("disputed")
    if _case_has_overdue_invoice(db, case.id):
        badges.append("overdue")
    if _case_has_draft_invoice(db, case.id, ym):
        badges.append("draft")

    month_inv = db.scalar(
        select(ClientInvoice).where(
            ClientInvoice.case_id == case.id,
            ClientInvoice.billing_month == ym,
            ClientInvoice.status.notin_([ClientInvoiceStatus.CANCELLED, ClientInvoiceStatus.VOID]),
        )
    )
    return {
        "caseId": case.id,
        "caseCode": case.case_code,
        "childName": case.child.full_name if case.child else "",
        "parentName": _parent_name_for_case(db, case),
        "parentEmail": _parent_email_for_case(db, case),
        "serviceType": case.service_type,
        "productModule": case.product_module,
        "billingModel": rule.billing_model.value if rule else None,
        "invoiceType": case.client_billing_mode.value if case.client_billing_mode else None,
        "assignedTherapists": _therapists_for_case(db, case.id),
        "lastInvoiceDate": last_inv.created_at.date().isoformat() if last_inv and last_inv.created_at else None,
        "currentMonthInvoiceStatus": month_inv.status.value if month_inv else None,
        "sessionsCompletedThisMonth": _sessions_completed_in_month(db, case.id, ym),
        "leavesThisMonth": _leaves_in_month(db, case.id, ym),
        "ledgerReadyCount": _ledger_ready_count(db, case.id, ym),
        "therapistSubmitted": _therapist_submitted_for_case_month(db, case.id, ym),
        "therapistPending": _therapist_pending_for_case_month(db, case.id, ym),
        "badges": badges,
        "actions": {
            "remindTherapist": _therapist_pending_for_case_month(db, case.id, ym),
            "useLedgerAnyway": _ledger_ready_count(db, case.id, ym) > 0
            and _therapist_pending_for_case_month(db, case.id, ym),
        },
    }


def _matches_queue(card: dict, queue: str, ym: str, db: Session, case_id: int) -> bool:
    if queue == "all":
        return True
    badges = set(card.get("badges") or [])
    if queue == "not_invoiced_this_month":
        return "not_invoiced" in badges
    if queue == "not_invoiced_last_30_days":
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent_inv = db.scalar(
            select(ClientInvoice.id).where(
                ClientInvoice.case_id == case_id,
                ClientInvoice.created_at >= cutoff,
                ClientInvoice.status.notin_([ClientInvoiceStatus.CANCELLED, ClientInvoiceStatus.VOID]),
            )
        )
        return recent_inv is None and (
            card.get("sessionsCompletedThisMonth", 0) > 0 or card.get("ledgerReadyCount", 0) > 0
        )
    if queue == "new_clients":
        return "new_client" in badges
    if queue == "ledger_ready":
        return "ledger_ready" in badges
    if queue == "therapist_submitted":
        return "therapist_submitted" in badges
    if queue == "therapist_pending":
        return "therapist_pending" in badges
    if queue == "disputed":
        return "disputed" in badges
    if queue == "overdue":
        return "overdue" in badges
    if queue == "draft":
        return "draft" in badges
    return True


def list_composer_cases(
    db: Session,
    *,
    billing_month: str,
    queue: str = "all",
    module: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    ym = normalize_billing_month(billing_month)
    q = (queue or "all").lower()
    if q not in COMPOSER_QUEUES:
        q = "all"

    stmt = (
        select(Case)
        .options(selectinload(Case.child))
        .where(Case.status == CaseStatus.ACTIVE)
        .order_by(Case.case_code)
    )
    if module:
        stmt = stmt.where(Case.product_module == module)
    cases = db.scalars(stmt).all()

    results: list[dict] = []
    tokens = [t for t in (search or "").strip().lower().split() if t]
    for case in cases:
        card = _build_case_card(db, case, ym)
        if tokens:
            hay = " ".join(
                [
                    card.get("caseCode") or "",
                    card.get("childName") or "",
                    card.get("parentName") or "",
                    card.get("parentEmail") or "",
                    card.get("serviceType") or "",
                ]
            ).lower()
            if not all(tok in hay for tok in tokens):
                continue
        if not _matches_queue(card, q, ym, db, case.id):
            continue
        results.append(card)
        if len(results) >= limit:
            break
    return results


def _suggested_lines_from_ledger(db: Session, case: Case, ym: str) -> list[dict]:
    rows = db.scalars(
        select(BillingLedger).where(
            BillingLedger.case_id == case.id,
            BillingLedger.ledger_month == ym,
            BillingLedger.billable_status.in_([BillableStatus.BILLABLE, BillableStatus.PENDING_REVIEW]),
            BillingLedger.client_invoice_id.is_(None),
        )
        .order_by(BillingLedger.event_date)
    ).all()
    suggested = []
    for row in rows:
        therapist_name = "—"
        if row.therapist_user_id:
            u = db.get(User, row.therapist_user_id)
            therapist_name = u.full_name if u and u.full_name else f"User {row.therapist_user_id}"
        suggested.append(
            {
                "ledgerId": row.id,
                "sessionDate": row.event_date.isoformat(),
                "therapistName": therapist_name,
                "therapistUserId": row.therapist_user_id,
                "serviceLabel": case.service_type,
                "sessionStatus": row.event_type.value.replace("_", " ").title(),
                "amountInr": float(row.total_inr),
                "taxableAmountInr": float(row.amount_inr),
                "gstRatePercent": float(row.gst_rate_percent) if row.gst_rate_percent is not None else None,
                "gstAmountInr": float(row.gst_amount_inr) if row.gst_amount_inr is not None else None,
                "lineItemType": "SESSION_CHARGE",
                "sessionId": row.session_id,
                "dailyLogId": row.daily_log_id,
            }
        )
    return suggested


def _therapist_submissions_for_case(db: Session, case_id: int, ym: str) -> list[dict]:
    invoices = db.scalars(
        select(Invoice)
        .join(InvoiceCaseLine, InvoiceCaseLine.invoice_id == Invoice.id)
        .where(
            InvoiceCaseLine.case_id == case_id,
            Invoice.month == ym,
        )
        .options(selectinload(Invoice.case_lines).selectinload(InvoiceCaseLine.session_lines))
    ).all()
    out: list[dict] = []
    for inv in invoices:
        therapist = db.get(User, inv.therapist_user_id)
        for cl in inv.case_lines:
            if cl.case_id != case_id:
                continue
            for sl in cl.session_lines:
                ledger_id = None
                if sl.session_id:
                    lr = db.scalar(
                        select(BillingLedger.id).where(
                            BillingLedger.case_id == case_id,
                            BillingLedger.session_id == sl.session_id,
                            BillingLedger.ledger_month == ym,
                        )
                    )
                    ledger_id = lr
                log_ok = sl.daily_log_id is not None or sl.session_id is not None
                out.append(
                    {
                        "invoiceId": inv.id,
                        "therapistUserId": inv.therapist_user_id,
                        "therapistName": therapist.full_name if therapist and therapist.full_name else "",
                        "sessionDate": sl.session_date.isoformat(),
                        "serviceLabel": cl.case_code,
                        "sessionStatus": sl.line_type.value,
                        "submittedAmountInr": float(sl.amount_inr),
                        "submittedOn": inv.created_at.isoformat() if inv.created_at else None,
                        "financeStatus": inv.status.value,
                        "sessionLogAvailable": log_ok,
                        "linkedLedgerId": ledger_id,
                        "sessionLineId": sl.id,
                    }
                )
    return out


def _session_overview_counts(db: Session, case_id: int, ym: str) -> dict:
    year_s, month_s = ym.split("-")[:2]
    y, m = int(year_s), int(month_s)

    def _count(status: SessionStatus | None = None) -> int:
        stmt = select(func.count(TherapySession.id)).where(
            TherapySession.case_id == case_id,
            extract("year", TherapySession.scheduled_date) == y,
            extract("month", TherapySession.scheduled_date) == m,
        )
        if status is not None:
            stmt = stmt.where(TherapySession.status == status)
        return int(db.scalar(stmt) or 0)

    completed = _count(SessionStatus.COMPLETED)
    cancelled = _count(SessionStatus.CANCELLED)
    rescheduled = _count(SessionStatus.RESCHEDULED)
    scheduled = _count()
    billable_ledger = int(
        db.scalar(
            select(func.count(BillingLedger.id)).where(
                BillingLedger.case_id == case_id,
                BillingLedger.ledger_month == ym,
                BillingLedger.billable_status.in_([BillableStatus.BILLABLE, BillableStatus.INVOICED]),
            )
        )
        or 0
    )
    return {
        "sessionsScheduled": scheduled,
        "sessionsCompleted": completed,
        "sessionsBillable": billable_ledger,
        "cancelledSessions": cancelled,
        "rescheduledSessions": rescheduled,
        "lateAddedSessions": 0,
    }


def _warnings_for_preview(
    db: Session, case_id: int, ym: str, suggested: list, ledger_rows: list
) -> list[dict]:
    warnings: list[dict] = []
    if _therapist_pending_for_case_month(db, case_id, ym):
        warnings.append(
            {
                "code": "THERAPIST_INVOICE_MISSING",
                "message": "Therapist has not submitted billing for this month.",
                "action": "remind_therapist",
            }
        )
    pending = sum(1 for r in ledger_rows if r.get("billableStatus") == "PENDING_REVIEW")
    if pending:
        warnings.append(
            {
                "code": "LEDGER_PENDING_REVIEW",
                "message": f"{pending} ledger row(s) pending finance review.",
                "action": "review_ledger",
            }
        )
    if not suggested and not ledger_rows:
        warnings.append(
            {
                "code": "NO_BILLABLE_ROWS",
                "message": "No billable ledger rows for this period.",
                "action": "manual_invoice",
            }
        )
    return warnings


def get_saved_preferences(db: Session, case_id: int) -> dict:
    from app.models.case_billing_preference import CaseBillingPreference

    pref = db.scalar(select(CaseBillingPreference).where(CaseBillingPreference.case_id == case_id))
    if pref:
        return {
            "invoiceType": pref.invoice_type,
            "gstApplicable": pref.gst_applicable,
            "gstRatePercent": float(pref.gst_rate_percent) if pref.gst_rate_percent is not None else None,
            "gatewayEnabled": pref.gateway_enabled,
            "dueDateOffsetDays": pref.due_date_offset_days,
            "paymentPolicyTemplate": pref.payment_policy_template,
            "source": "case_profile",
        }
    last = db.scalar(
        select(ClientInvoice)
        .where(ClientInvoice.case_id == case_id)
        .order_by(ClientInvoice.created_at.desc())
        .limit(1)
    )
    if last:
        return {
            "invoiceType": last.invoice_type.value,
            "gatewayEnabled": bool(getattr(last, "gateway_enabled", False)),
            "paymentPolicyTemplate": last.payment_policy_snapshot,
            "source": "last_invoice",
        }
    return {}


def get_composer_preview(db: Session, *, case_id: int, billing_month: str) -> dict:
    ym = normalize_billing_month(billing_month)
    case = db.scalar(select(Case).where(Case.id == case_id).options(selectinload(Case.child)))
    if not case:
        raise ValueError("Case not found")

    rule = _resolve_rule_for_case(db, case)
    ledger_rows = billing_ledger_service.list_ledger(db, ledger_month=ym, case_id=case_id)
    suggested = _suggested_lines_from_ledger(db, case, ym)
    therapist_submissions = _therapist_submissions_for_case(db, case_id, ym)
    reconcile = billing_ledger_service.reconcile_month(db, case_id=case_id, billing_month=ym)
    session_counts = _session_overview_counts(db, case_id, ym)
    leaves_total = _leaves_in_month(db, case_id, ym)

    subtotal = sum(float(r.get("amountInr") or 0) for r in suggested)
    tax = sum(float(r.get("gstAmountInr") or 0) for r in suggested if r.get("gstAmountInr"))
    total = sum(float(r.get("amountInr") or 0) for r in suggested)

    start, end = _month_bounds(ym)
    due_suggestion = (end + timedelta(days=10)).isoformat()

    inv_type = "POSTPAID"
    if case.client_billing_mode:
        inv_type = case.client_billing_mode.value
    elif rule:
        if rule.billing_model.value == "PREPAID_PACKAGE":
            inv_type = "PREPAID"

    warnings = _warnings_for_preview(db, case_id, ym, suggested, ledger_rows)

    return {
        "includeFinanceFields": True,
        "case": {
            "id": case.id,
            "caseCode": case.case_code,
            "childName": case.child.full_name if case.child else "",
            "parentName": _parent_name_for_case(db, case),
            "service": case.product_module,
            "serviceType": case.service_type,
            "assignedTherapists": _therapists_for_case(db, case.id),
        },
        "billingRule": {
            "billingModel": rule.billing_model.value if rule else None,
            "invoiceType": inv_type,
            "gstApplicable": bool(rule.gst_applicable) if rule else False,
            "gstRatePercent": float(rule.gst_rate_percent) if rule and rule.gst_rate_percent is not None else None,
            "includedPaidLeaves": rule.included_paid_leaves if rule else None,
            "unpaidLeaveDeductionMethod": rule.unpaid_leave_deduction_method if rule else None,
            "productName": rule.product_name if rule else None,
        },
        "period": {
            "billingMonth": ym,
            "billingMonthLabel": datetime.strptime(ym, "%Y-%m").strftime("%b %Y"),
            "dueDateSuggestion": due_suggestion,
        },
        "overview": {
            **session_counts,
            "leavesTotal": leaves_total,
            "paidLeaves": None,
            "unpaidLeaves": leaves_total,
            "subtotal": round(subtotal, 2),
            "taxAmount": round(tax, 2),
            "total": round(total, 2),
            "therapistPayoutTotal": reconcile.get("therapistPayoutTotalInr", 0),
            "estimatedMargin": reconcile.get("marginInr", 0),
        },
        "ledgerRows": ledger_rows,
        "therapistSubmissions": therapist_submissions,
        "suggestedLineItems": suggested,
        "warnings": warnings,
        "savedPreferences": get_saved_preferences(db, case_id),
        "defaultPaymentPolicy": DEFAULT_PAYMENT_POLICY,
    }


def _resolve_rule_for_case(db: Session, case: Case) -> ProductBillingRule | None:
    if case.product_billing_rule_id:
        return product_billing_rule_service.get_rule(db, case.product_billing_rule_id)
    return db.scalars(
        select(ProductBillingRule)
        .where(
            ProductBillingRule.product_module == case.product_module,
            ProductBillingRule.active.is_(True),
        )
        .order_by(ProductBillingRule.id)
    ).first()


def remind_therapist(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    actor_user_id: int,
    message: Optional[str] = None,
) -> dict:
    ym = normalize_billing_month(billing_month)
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    therapists = _therapists_for_case(db, case_id)
    body = message or f"Please submit your billing for {case.case_code} ({ym})."
    notified = 0
    for t in therapists:
        notification_service.create_notification(
            db,
            user_id=t["userId"],
            title=f"Billing reminder — {case.case_code}",
            body=body,
            entity_type="case",
            entity_id=case_id,
        )
        notified += 1
    return {"queued": notified > 0, "notifiedCount": notified, "logged": True}
