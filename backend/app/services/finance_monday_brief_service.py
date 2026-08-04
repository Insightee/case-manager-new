"""Monday finance briefing — compose-only, no new money math."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.services import billing_composer_service, client_billing_service, finance_overview_service, therapist_payout_queue_service


def monday_finance_brief(db: Session, *, billing_month: str | None = None) -> dict:
    ym = (
        billing_composer_service.normalize_billing_month(billing_month)
        if billing_month
        else None
    )

    receivables = client_billing_service.admin_receivables_summary(
        db,
        month=ym,
    )
    payout_queue = therapist_payout_queue_service.admin_payout_queue_summary(
        db,
        month=ym or billing_composer_service.normalize_billing_month(date.today().strftime("%Y-%m")),
    )
    overview = finance_overview_service.finance_overview_summary(
        db,
        billing_month=ym or billing_composer_service.normalize_billing_month(date.today().strftime("%Y-%m")),
    )

    recv_totals = receivables.get("totals") or {}
    pay_totals = payout_queue.get("totals") or {}
    queues = overview.get("queues") or {}

    money_in = {
        "collectibleOutstandingInr": recv_totals.get("outstandingInr"),
        "overdueCount": recv_totals.get("overdueCount"),
        "overdueInr": recv_totals.get("overdueInr"),
        "paymentClaimsPending": queues.get("paymentClaimsPending"),
        "openClientDisputes": queues.get("openDisputes"),
        "packagesLowBalance": None,
        "packagesLowBalanceNote": "Not yet available",
    }

    money_out = {
        "statementsPendingApproval": pay_totals.get("pendingCount"),
        "disputedQueriedCount": pay_totals.get("disputedCount"),
        "cleanReadyCount": pay_totals.get("approvedCount"),
        "totalPayableInr": pay_totals.get("totalPayableNowInr"),
        "needsReviewCount": pay_totals.get("needsReviewCount"),
        "approveDisabledNote": "Approve & queue payout is enabled after cutover",
    }

    top_items: list[dict] = []
    if money_in["paymentClaimsPending"]:
        top_items.append(
            {
                "kind": "payment_claim",
                "label": f"{money_in['paymentClaimsPending']} payment claim(s) pending review",
                "href": "/admin/invoices?tab=payments&claims=pending",
            }
        )
    if money_in["openClientDisputes"]:
        top_items.append(
            {
                "kind": "client_dispute",
                "label": f"{money_in['openClientDisputes']} open client dispute(s)",
                "href": "/admin/invoices?tab=disputes",
            }
        )
    if money_out["disputedQueriedCount"]:
        top_items.append(
            {
                "kind": "therapist_dispute",
                "label": f"{money_out['disputedQueriedCount']} therapist statement(s) disputed or queried",
                "href": "/admin/therapist-payouts?sub=payouts&view=queue&status=QUERIED",
            }
        )
    if money_out["statementsPendingApproval"]:
        top_items.append(
            {
                "kind": "payout_pending",
                "label": f"{money_out['statementsPendingApproval']} therapist statement(s) pending approval",
                "href": "/admin/therapist-payouts?sub=payouts&view=queue&status=IN_REVIEW",
            }
        )

    most_important = top_items[0] if top_items else None

    return {
        "billingMonth": ym,
        "scopeAllMonths": ym is None,
        "moneyIn": money_in,
        "moneyOut": money_out,
        "thisWeek": {
            "topItems": top_items[:5],
            "mostImportant": most_important,
        },
        "links": {
            "receivables": "/admin/invoices?tab=receivables",
            "clientDisputes": "/admin/invoices?tab=disputes",
            "paymentClaims": "/admin/invoices?tab=payments&claims=pending",
            "therapistPayoutQueue": "/admin/therapist-payouts?sub=payouts&view=queue",
        },
        "sources": {
            "receivablesEndpoint": "/api/v1/admin/client-billing/receivables",
            "payoutQueueEndpoint": "/api/v1/admin/therapist-payouts/queue",
            "overviewEndpoint": "/api/v1/admin/finance-overview/summary",
        },
    }
