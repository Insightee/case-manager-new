"""Aggregated finance overview counts for admin hub."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus
from app.models.client_billing import (
    BillingDispute,
    BillingDisputeStatus,
    ClientInvoice,
    ClientInvoiceStatus,
    ClientPayment,
    ClientPaymentStatus,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ledger_billing import BillableStatus, BillingLedger
from app.services import billing_composer_service


def finance_overview_summary(db: Session, *, billing_month: str | None = None) -> dict:
    ym = billing_composer_service.normalize_billing_month(billing_month or date.today().strftime("%Y-%m"))

    not_invoiced = len(
        billing_composer_service.list_composer_cases(
            db, billing_month=ym, queue="not_invoiced_this_month", limit=500
        )
    )
    ledger_ready = len(
        billing_composer_service.list_composer_cases(db, billing_month=ym, queue="ledger_ready", limit=500)
    )
    therapist_pending = len(
        billing_composer_service.list_composer_cases(
            db, billing_month=ym, queue="therapist_pending", limit=500
        )
    )
    therapist_submitted = len(
        billing_composer_service.list_composer_cases(
            db, billing_month=ym, queue="therapist_submitted", limit=500
        )
    )
    draft_cases = len(
        billing_composer_service.list_composer_cases(db, billing_month=ym, queue="draft", limit=500)
    )

    payouts_in_review = int(
        db.scalar(
            select(func.count(Invoice.id)).where(Invoice.status == InvoiceStatus.IN_REVIEW)
        )
        or 0
    )
    payouts_approved_unpaid = int(
        db.scalar(
            select(func.count(Invoice.id)).where(Invoice.status == InvoiceStatus.APPROVED)
        )
        or 0
    )

    claims_pending = int(
        db.scalar(
            select(func.count(ClientPayment.id)).where(
                ClientPayment.payment_status == ClientPaymentStatus.PENDING_REVIEW
            )
        )
        or 0
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

    unpaid_invoices = int(
        db.scalar(
            select(func.count(ClientInvoice.id)).where(
                ClientInvoice.status.in_(
                    [
                        ClientInvoiceStatus.SENT,
                        ClientInvoiceStatus.GENERATED,
                        ClientInvoiceStatus.PARTIALLY_PAID,
                        ClientInvoiceStatus.OVERDUE,
                    ]
                )
            )
        )
        or 0
    )

    active_cases = int(
        db.scalar(select(func.count(Case.id)).where(Case.status == CaseStatus.ACTIVE)) or 0
    )

    pending_ledger = int(
        db.scalar(
            select(func.count(BillingLedger.id)).where(
                BillingLedger.ledger_month == ym,
                BillingLedger.billable_status == BillableStatus.PENDING_REVIEW,
            )
        )
        or 0
    )

    return {
        "billingMonth": ym,
        "activeCases": active_cases,
        "queues": {
            "notInvoicedThisMonth": not_invoiced,
            "ledgerReady": ledger_ready,
            "therapistPending": therapist_pending,
            "therapistSubmitted": therapist_submitted,
            "draftInvoices": draft_cases,
            "payoutsInReview": payouts_in_review,
            "payoutsApprovedUnpaid": payouts_approved_unpaid,
            "paymentClaimsPending": claims_pending,
            "openDisputes": open_disputes,
            "unpaidClientInvoices": unpaid_invoices,
            "ledgerPendingReview": pending_ledger,
        },
        "links": {
            "composerNotInvoiced": f"/admin/invoices/compose?billing_month={ym}&queue=not_invoiced_this_month",
            "composerLedgerReady": f"/admin/invoices/compose?billing_month={ym}&queue=ledger_ready",
            "composerTherapistPending": f"/admin/invoices/compose?billing_month={ym}&queue=therapist_pending",
            "clientInvoices": "/admin/invoices?tab=client",
            "clientPayments": "/admin/invoices?tab=payments",
            "therapistPayouts": "/admin/therapist-payouts?sub=payouts&status=IN_REVIEW",
            "disputes": "/admin/invoices?tab=disputes",
        },
    }
