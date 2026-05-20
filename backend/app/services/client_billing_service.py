from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.client_billing import (
    BillingDispute,
    BillingDisputeStatus,
    CarePackage,
    CarePackageStatus,
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceStatus,
    ClientInvoiceType,
    ClientPayment,
    PaymentMethod,
)
from app.models.daily_log import DailyLog
from app.models.user import User
from app.core.config import settings
from app.services import email_service, notification_service, parent_service


def _parent_case_ids(db: Session, user_id: int) -> list[int]:
    child_ids = parent_service.child_ids_for_parent(db, user_id)
    if not child_ids:
        return []
    return list(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())


def _payment_bucket(inv: ClientInvoice) -> str:
    if inv.status == ClientInvoiceStatus.DISPUTED:
        return "disputed"
    balance = float(inv.total_inr) - float(inv.amount_paid_inr or 0)
    if inv.status == ClientInvoiceStatus.PAID or balance <= 0:
        return "paid"
    if float(inv.amount_paid_inr or 0) > 0:
        return "partial"
    return "unpaid"


def _invoice_is_overdue(inv: ClientInvoice, balance: float) -> bool:
    if inv.status == ClientInvoiceStatus.DISPUTED or balance <= 0:
        return False
    if not inv.due_date:
        return False
    return date.today() > inv.due_date


def _serialize_invoice_summary(inv: ClientInvoice, case: Case | None) -> dict:
    balance = float(inv.total_inr) - float(inv.amount_paid_inr or 0)
    bucket = _payment_bucket(inv)
    is_overdue = _invoice_is_overdue(inv, balance)
    return {
        "id": inv.id,
        "invoiceNumber": inv.invoice_number,
        "caseId": case.case_code if case else "",
        "caseDbId": inv.case_id,
        "childName": case.child.full_name if case and case.child else "",
        "month": inv.billing_month,
        "billingMonth": inv.billing_month,
        "serviceType": inv.service_type,
        "productModule": inv.product_module,
        "invoiceType": inv.invoice_type.value,
        "status": inv.status.value.lower(),
        "paymentBucket": bucket,
        "dueDate": inv.due_date.isoformat() if inv.due_date else None,
        "totalInr": float(inv.total_inr),
        "amountPaidInr": float(inv.amount_paid_inr or 0),
        "balanceInr": max(0, balance),
        "hasDispute": inv.status == ClientInvoiceStatus.DISPUTED,
        "isOverdue": is_overdue,
        "createdAt": inv.created_at.isoformat() if inv.created_at else None,
    }


def list_invoices(
    db: Session,
    user: User,
    *,
    month: Optional[str] = None,
    case_id: Optional[int] = None,
    service: Optional[str] = None,
    payment_bucket: Optional[str] = None,
) -> list[dict]:
    case_ids = _parent_case_ids(db, user.id)
    if not case_ids:
        return []
    if case_id is not None:
        if case_id not in case_ids:
            return []
        case_ids = [case_id]

    stmt = select(ClientInvoice).where(
        ClientInvoice.parent_user_id == user.id,
        ClientInvoice.case_id.in_(case_ids),
    )
    if month:
        stmt = stmt.where(ClientInvoice.billing_month == month)
    if service:
        svc = service.lower()
        stmt = stmt.where(
            (ClientInvoice.service_type.ilike(f"%{svc}%")) | (ClientInvoice.product_module.ilike(f"%{svc}%"))
        )

    rows = db.scalars(stmt.order_by(ClientInvoice.created_at.desc())).all()
    cases = {c.id: c for c in db.scalars(select(Case).where(Case.id.in_(case_ids))).all()}
    result = []
    for inv in rows:
        item = _serialize_invoice_summary(inv, cases.get(inv.case_id))
        if payment_bucket:
            b = item["paymentBucket"]
            if payment_bucket == "needs_payment":
                if b not in ("unpaid", "partial"):
                    continue
            elif b != payment_bucket:
                continue
        result.append(item)
    return result


def _sort_invoices_for_parent_view(items: list[dict]) -> list[dict]:
    """Unpaid/partial first; overdue before not overdue; sooner due dates first; then newest."""

    def tier(pb: str) -> int:
        if pb in ("unpaid", "partial"):
            return 0
        if pb == "disputed":
            return 1
        return 2

    def key(inv: dict) -> tuple:
        t = tier(inv["paymentBucket"])
        od = 0 if inv.get("isOverdue") else 1
        due = inv.get("dueDate") or "9999-12-31"
        created = inv.get("createdAt") or ""
        return (t, od, due, created)

    return sorted(items, key=key)


def get_dashboard(
    db: Session,
    user: User,
    *,
    month: Optional[str] = None,
    case_id: Optional[int] = None,
    service: Optional[str] = None,
    payment_bucket: Optional[str] = None,
) -> dict:
    all_invoices = list_invoices(db, user)
    invoices = list_invoices(
        db, user, month=month, case_id=case_id, service=service, payment_bucket=payment_bucket
    )
    invoices = _sort_invoices_for_parent_view(invoices)
    packages = list_packages(db, user)
    due_total = sum(i["balanceInr"] for i in all_invoices if i["paymentBucket"] in ("unpaid", "partial"))
    needs_payment = [i for i in all_invoices if i["paymentBucket"] in ("unpaid", "partial")]
    overdue_ct = sum(1 for i in needs_payment if i.get("isOverdue"))
    disputed = sum(1 for i in all_invoices if i["paymentBucket"] == "disputed")
    months = sorted({i["billingMonth"] for i in all_invoices}, reverse=True)
    children = sorted({f"{i['childName']}|{i['caseDbId']}" for i in all_invoices if i.get("childName")})
    services = sorted({i["serviceType"] for i in all_invoices})
    return {
        "summary": {
            "invoiceCount": len(all_invoices),
            "dueTotalInr": due_total,
            "needsPaymentCount": len(needs_payment),
            "overdueCount": overdue_ct,
            "disputedCount": disputed,
            "activePackages": sum(1 for p in packages if p["status"] == "active"),
        },
        "invoices": invoices,
        "packages": packages,
        "filterOptions": {
            "months": months,
            "children": [
                {"caseDbId": int(c.split("|")[1]), "label": c.split("|")[0]} for c in children if "|" in c
            ],
            "services": services,
        },
    }


def list_packages(db: Session, user: User) -> list[dict]:
    case_ids = _parent_case_ids(db, user.id)
    if not case_ids:
        return []
    rows = db.scalars(
        select(CarePackage)
        .where(CarePackage.parent_user_id == user.id, CarePackage.case_id.in_(case_ids))
        .order_by(CarePackage.validity_end.asc().nullslast())
    ).all()
    cases = {c.id: c for c in db.scalars(select(Case).where(Case.id.in_(case_ids))).all()}
    result = []
    for pkg in rows:
        case = cases.get(pkg.case_id)
        remaining = max(0, pkg.total_sessions - pkg.used_sessions)
        result.append(
            {
                "id": pkg.id,
                "name": pkg.name,
                "caseId": case.case_code if case else "",
                "caseDbId": pkg.case_id,
                "childName": case.child.full_name if case and case.child else "",
                "totalSessions": pkg.total_sessions,
                "usedSessions": pkg.used_sessions,
                "remainingSessions": remaining,
                "validityEnd": pkg.validity_end.isoformat() if pkg.validity_end else None,
                "serviceLabel": pkg.service_label,
                "status": pkg.status.value.lower(),
            }
        )
    return result


def get_invoice_detail(db: Session, user: User, invoice_id: int) -> dict:
    inv = db.scalar(
        select(ClientInvoice)
        .where(ClientInvoice.id == invoice_id, ClientInvoice.parent_user_id == user.id)
        .options(selectinload(ClientInvoice.lines), selectinload(ClientInvoice.payments), selectinload(ClientInvoice.disputes))
    )
    if not inv:
        raise ValueError("Invoice not found")
    case = parent_service.get_parent_case(db, user, inv.case_id)
    if not case:
        raise ValueError("Invoice not found")

    lines = sorted(inv.lines, key=lambda x: (x.session_date, x.sort_order))
    detail = _serialize_invoice_summary(inv, case)
    detail.update(
        {
            "subtotalInr": float(inv.subtotal_inr or 0),
            "taxInr": float(inv.tax_inr or 0),
            "discountInr": float(inv.discount_inr or 0),
            "packageDeductionInr": float(inv.package_deduction_inr or 0),
            "adjustmentInr": float(inv.adjustment_inr or 0),
            "notes": inv.notes,
            "lines": [
                {
                    "id": line.id,
                    "sessionDate": line.session_date.isoformat(),
                    "therapistName": line.therapist_name,
                    "serviceLabel": line.service_label,
                    "sessionStatus": line.session_status,
                    "amountInr": float(line.amount_inr),
                    "packageDeducted": line.package_deducted,
                    "parentSummary": line.parent_summary,
                    "sessionId": line.session_id,
                    "dailyLogId": line.daily_log_id,
                }
                for line in lines
            ],
            "payments": [
                {
                    "id": p.id,
                    "amountInr": float(p.amount_inr),
                    "method": p.method.value,
                    "reference": p.reference,
                    "paidAt": p.paid_at.isoformat() if p.paid_at else None,
                }
                for p in inv.payments
            ],
            "disputes": [
                {
                    "id": d.id,
                    "reasonCode": d.reason_code,
                    "message": d.message,
                    "status": d.status.value.lower(),
                    "adminResolution": d.admin_resolution,
                    "createdAt": d.created_at.isoformat() if d.created_at else None,
                }
                for d in inv.disputes
            ],
        }
    )
    return detail


def get_line_session_detail(db: Session, user: User, line_id: int) -> dict:
    line = db.get(ClientInvoiceLine, line_id)
    if not line:
        raise ValueError("Line not found")
    inv = db.get(ClientInvoice, line.client_invoice_id)
    if not inv or inv.parent_user_id != user.id:
        raise ValueError("Line not found")
    parent_service.get_parent_case(db, user, inv.case_id)

    log = db.get(DailyLog, line.daily_log_id) if line.daily_log_id else None
    attendance = log.attendance_status if log else None
    activities = log.activities_done if log else line.parent_summary

    return {
        "lineId": line.id,
        "invoiceId": inv.id,
        "sessionDate": line.session_date.isoformat(),
        "therapistName": line.therapist_name,
        "serviceLabel": line.service_label,
        "sessionStatus": line.session_status,
        "amountInr": float(line.amount_inr),
        "attendance": attendance,
        "activitiesSummary": activities,
        "goalsAddressed": log.goals_addressed if log else None,
        "followUps": log.follow_ups if log else None,
    }


def create_dispute(
    db: Session,
    user: User,
    invoice_id: int,
    reason_code: str,
    message: str,
    line_id: Optional[int] = None,
) -> dict:
    inv = db.get(ClientInvoice, invoice_id)
    if not inv or inv.parent_user_id != user.id:
        raise ValueError("Invoice not found")
    if line_id:
        line = db.get(ClientInvoiceLine, line_id)
        if not line or line.client_invoice_id != inv.id:
            raise ValueError("Invalid line")
    dispute = BillingDispute(
        client_invoice_id=inv.id,
        client_invoice_line_id=line_id,
        parent_user_id=user.id,
        reason_code=reason_code,
        message=message,
        status=BillingDisputeStatus.OPEN,
    )
    inv.status = ClientInvoiceStatus.DISPUTED
    db.add(dispute)
    db.flush()

    case = db.get(Case, inv.case_id)
    if case and case.case_manager_user_id:
        notification_service.create_notification(
            db,
            user_id=case.case_manager_user_id,
            title="Invoice dispute raised",
            body=f"{inv.invoice_number}: {message[:200]}",
            entity_type="client_invoice",
            entity_id=inv.id,
        )
    return {"id": dispute.id, "status": dispute.status.value.lower()}


def record_payment(
    db: Session,
    invoice_id: int,
    amount_inr: float,
    method: str,
    reference: Optional[str],
    notes: Optional[str],
    recorded_by_user_id: int,
) -> ClientInvoice:
    inv = db.get(ClientInvoice, invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    payment = ClientPayment(
        client_invoice_id=inv.id,
        amount_inr=amount_inr,
        method=PaymentMethod(method),
        reference=reference,
        notes=notes,
        recorded_by_user_id=recorded_by_user_id,
    )
    db.add(payment)
    inv.amount_paid_inr = float(inv.amount_paid_inr or 0) + amount_inr
    balance = float(inv.total_inr) - float(inv.amount_paid_inr)
    if balance <= 0:
        inv.status = ClientInvoiceStatus.PAID
    elif float(inv.amount_paid_inr) > 0:
        inv.status = ClientInvoiceStatus.PARTIALLY_PAID
    db.flush()
    notification_service.create_notification(
        db,
        user_id=inv.parent_user_id,
        title="Payment recorded",
        body=f"₹{int(amount_inr):,} received for {inv.invoice_number}",
        entity_type="client_invoice",
        entity_id=inv.id,
    )
    return inv


def resolve_dispute(
    db: Session,
    dispute_id: int,
    status: str,
    resolution: str,
    adjustment_inr: Optional[float] = None,
) -> BillingDispute:
    dispute = db.get(BillingDispute, dispute_id)
    if not dispute:
        raise ValueError("Dispute not found")
    inv = db.get(ClientInvoice, dispute.client_invoice_id)
    dispute.status = BillingDisputeStatus(status)
    dispute.admin_resolution = resolution
    dispute.resolved_at = datetime.now(timezone.utc)
    if adjustment_inr is not None and inv:
        inv.adjustment_inr = float(inv.adjustment_inr or 0) + adjustment_inr
        inv.total_inr = max(0, float(inv.total_inr) + adjustment_inr)
    if inv:
        open_disputes = db.scalars(
            select(BillingDispute).where(
                BillingDispute.client_invoice_id == inv.id,
                BillingDispute.status.in_([BillingDisputeStatus.OPEN, BillingDisputeStatus.UNDER_REVIEW]),
                BillingDispute.id != dispute.id,
            )
        ).all()
        if not open_disputes:
            balance = float(inv.total_inr) - float(inv.amount_paid_inr or 0)
            if balance <= 0:
                inv.status = ClientInvoiceStatus.PAID
            elif float(inv.amount_paid_inr or 0) > 0:
                inv.status = ClientInvoiceStatus.PARTIALLY_PAID
            else:
                inv.status = ClientInvoiceStatus.SENT
    db.flush()
    if inv:
        notification_service.create_notification(
            db,
            user_id=inv.parent_user_id,
            title="Dispute updated",
            body=resolution[:200],
            entity_type="billing_dispute",
            entity_id=dispute.id,
        )
    return dispute


def notify_parent_invoice_issued(db: Session, invoice_id: int, *, resend: bool = False) -> dict:
    """Email + in-app notice. Idempotent unless resend=True. Sets sent_at and promotes GENERATED → SENT."""
    inv = db.get(ClientInvoice, invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    parent = db.get(User, inv.parent_user_id)
    if not parent:
        raise ValueError("Parent not found")
    if inv.sent_at and not resend:
        return {"status": "already_sent", "sent_at": inv.sent_at.isoformat()}

    case = db.get(Case, inv.case_id)
    child_name = case.child.full_name if case and case.child else "Your child"
    balance = float(inv.total_inr) - float(inv.amount_paid_inr or 0)
    is_overdue = _invoice_is_overdue(inv, balance)
    due_str = inv.due_date.strftime("%d %b %Y") if inv.due_date else None
    url = f"{settings.frontend_url.rstrip('/')}/parent/billing"

    email_service.parent_invoice_ready_email(
        to=parent.email,
        parent_name=parent.full_name or "there",
        invoice_number=inv.invoice_number,
        child_name=child_name,
        total_inr=float(inv.total_inr),
        balance_inr=balance,
        due_date_str=due_str,
        is_overdue=is_overdue,
        payments_url=url,
    )
    now = datetime.now(timezone.utc)
    inv.sent_at = now
    if inv.status == ClientInvoiceStatus.GENERATED:
        inv.status = ClientInvoiceStatus.SENT
    if balance > 0:
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title=f"Invoice {inv.invoice_number} — payment due",
            body=f"₹{balance:,.0f} outstanding for {child_name}. Open Payments to review and pay.",
            entity_type="client_invoice",
            entity_id=inv.id,
        )
    else:
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title=f"Invoice {inv.invoice_number}",
            body=f"Your invoice for {child_name} is available in Payments.",
            entity_type="client_invoice",
            entity_id=inv.id,
        )
    db.flush()
    return {"status": "sent", "sent_at": inv.sent_at.isoformat() if inv.sent_at else None}
