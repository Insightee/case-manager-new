from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
import secrets
import shutil

from fastapi import UploadFile

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.child import Child
from app.models.parent import ParentGuardian
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
    ClientPaymentStatus,
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
                    "paymentStatus": p.payment_status.value.lower(),
                    "proofFileName": p.proof_file_name,
                    "hasProof": bool(p.proof_file_path),
                    "rejectionNote": p.rejection_note,
                    "notes": p.notes,
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
        payment_status=ClientPaymentStatus.CONFIRMED,
        confirmed_by_user_id=recorded_by_user_id,
        confirmed_at=datetime.now(timezone.utc),
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


def _parents_for_case(db: Session, case_id: int) -> list[int]:
    case = db.get(Case, case_id)
    if not case:
        return []
    parents = db.scalars(
        select(ParentGuardian)
        .join(ParentGuardian.children)
        .where(Child.id == case.child_id)
    ).all()
    return list({pg.user_id for pg in parents})


def _next_invoice_number(db: Session) -> str:
    year = date.today().year
    prefix = f"INV-{year}-"
    existing = db.scalars(
        select(ClientInvoice.invoice_number).where(ClientInvoice.invoice_number.like(f"{prefix}%"))
    ).all()
    nums = []
    for num in existing:
        try:
            nums.append(int(num.split("-")[-1]))
        except ValueError:
            pass
    seq = (max(nums) + 1) if nums else 1
    return f"{prefix}{seq:04d}"


def _admin_invoice_summary_row(inv: ClientInvoice, case: Case | None, parent: User | None) -> dict:
    base = _serialize_invoice_summary(inv, case)
    base["status"] = inv.status.value
    base["parentUserId"] = inv.parent_user_id
    base["parentName"] = parent.full_name if parent else ""
    base["parentEmail"] = parent.email if parent else ""
    base["sentAt"] = inv.sent_at.isoformat() if inv.sent_at else None
    base["notes"] = inv.notes
    return base


def admin_list_invoices(
    db: Session,
    *,
    month: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict]:
    stmt = select(ClientInvoice).order_by(ClientInvoice.created_at.desc())
    if month:
        stmt = stmt.where(ClientInvoice.billing_month == month)
    if case_id:
        stmt = stmt.where(ClientInvoice.case_id == case_id)
    if status:
        try:
            stmt = stmt.where(ClientInvoice.status == ClientInvoiceStatus(status))
        except ValueError:
            pass
    if module:
        stmt = stmt.where(ClientInvoice.product_module == module)

    rows = db.scalars(stmt).all()
    case_ids = {r.case_id for r in rows}
    cases = {c.id: c for c in db.scalars(select(Case).where(Case.id.in_(case_ids))).all()} if case_ids else {}
    parent_ids = {r.parent_user_id for r in rows}
    parents = {u.id: u for u in db.scalars(select(User).where(User.id.in_(parent_ids))).all()} if parent_ids else {}

    result = []
    for inv in rows:
        case = cases.get(inv.case_id)
        if case and case.child_id:
            case = db.scalar(
                select(Case).where(Case.id == inv.case_id).options(selectinload(Case.child))
            ) or case
        parent = parents.get(inv.parent_user_id)
        item = _admin_invoice_summary_row(inv, case, parent)
        if search:
            q = search.lower()
            hay = " ".join(
                [
                    item.get("invoiceNumber", ""),
                    item.get("childName", ""),
                    item.get("caseId", ""),
                    item.get("parentName", ""),
                    item.get("parentEmail", ""),
                    item.get("billingMonth", ""),
                ]
            ).lower()
            if q not in hay:
                continue
        result.append(item)
    return result


def admin_get_invoice_detail(db: Session, invoice_id: int) -> dict:
    inv = db.scalar(
        select(ClientInvoice)
        .where(ClientInvoice.id == invoice_id)
        .options(
            selectinload(ClientInvoice.lines),
            selectinload(ClientInvoice.payments),
            selectinload(ClientInvoice.disputes),
        )
    )
    if not inv:
        raise ValueError("Invoice not found")
    case = db.scalar(select(Case).where(Case.id == inv.case_id).options(selectinload(Case.child)))
    parent = db.get(User, inv.parent_user_id)
    lines = sorted(inv.lines, key=lambda x: (x.session_date, x.sort_order))
    detail = _admin_invoice_summary_row(inv, case, parent)
    detail.update(
        {
            "subtotalInr": float(inv.subtotal_inr or 0),
            "taxInr": float(inv.tax_inr or 0),
            "discountInr": float(inv.discount_inr or 0),
            "packageDeductionInr": float(inv.package_deduction_inr or 0),
            "adjustmentInr": float(inv.adjustment_inr or 0),
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
                    "paymentStatus": p.payment_status.value.lower(),
                    "proofFileName": p.proof_file_name,
                    "hasProof": bool(p.proof_file_path),
                    "rejectionNote": p.rejection_note,
                    "notes": p.notes,
                }
                for p in inv.payments
            ],
            "disputes": [
                {
                    "id": d.id,
                    "reasonCode": d.reason_code,
                    "message": d.message,
                    "status": d.status.value,
                    "adminResolution": d.admin_resolution,
                    "createdAt": d.created_at.isoformat() if d.created_at else None,
                    "resolvedAt": d.resolved_at.isoformat() if d.resolved_at else None,
                }
                for d in inv.disputes
            ],
        }
    )
    return detail


def admin_create_invoice(
    db: Session,
    *,
    case_id: int,
    invoice_type: str,
    billing_month: str,
    due_date: Optional[date],
    lines: list[dict],
    notes: Optional[str],
    discount_inr: float,
    admin_user_id: int,
) -> ClientInvoice:
    case = db.scalar(select(Case).where(Case.id == case_id).options(selectinload(Case.child)))
    if not case:
        raise ValueError("Case not found")
    parent_ids = _parents_for_case(db, case_id)
    if not parent_ids:
        raise ValueError("No parent linked to this case")
    parent_user_id = parent_ids[0]

    subtotal = sum(float(ln.get("amount_inr", 0)) for ln in lines)
    total = max(0, subtotal - float(discount_inr or 0))

    inv = ClientInvoice(
        invoice_number=_next_invoice_number(db),
        parent_user_id=parent_user_id,
        case_id=case_id,
        invoice_type=ClientInvoiceType(invoice_type),
        status=ClientInvoiceStatus.DRAFT,
        billing_month=billing_month,
        service_type=case.service_type,
        product_module=case.product_module,
        due_date=due_date,
        subtotal_inr=subtotal,
        discount_inr=discount_inr or 0,
        total_inr=total,
        notes=notes,
    )
    db.add(inv)
    db.flush()

    for i, ln in enumerate(lines):
        db.add(
            ClientInvoiceLine(
                client_invoice_id=inv.id,
                session_id=ln.get("session_id"),
                daily_log_id=ln.get("daily_log_id"),
                session_date=ln["session_date"],
                therapist_name=ln["therapist_name"],
                service_label=ln["service_label"],
                session_status=ln.get("session_status", "COMPLETED"),
                amount_inr=ln["amount_inr"],
                parent_summary=ln.get("parent_summary"),
                sort_order=i,
            )
        )
    db.flush()
    return inv


def admin_update_invoice(db: Session, invoice_id: int, updates: dict) -> ClientInvoice:
    inv = db.get(ClientInvoice, invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    if inv.status not in (ClientInvoiceStatus.DRAFT, ClientInvoiceStatus.GENERATED):
        if updates.get("status") not in (None, inv.status.value):
            raise ValueError("Only draft or generated invoices can be edited")

    if "due_date" in updates and updates["due_date"] is not None:
        inv.due_date = updates["due_date"]
    if "notes" in updates:
        inv.notes = updates["notes"]
    if "discount_inr" in updates and updates["discount_inr"] is not None:
        inv.discount_inr = updates["discount_inr"]
        inv.total_inr = max(
            0,
            float(inv.subtotal_inr or 0)
            - float(inv.discount_inr or 0)
            - float(inv.package_deduction_inr or 0)
            + float(inv.adjustment_inr or 0),
        )
    if "adjustment_inr" in updates and updates["adjustment_inr"] is not None:
        inv.adjustment_inr = updates["adjustment_inr"]
        inv.total_inr = max(
            0,
            float(inv.subtotal_inr or 0)
            - float(inv.discount_inr or 0)
            - float(inv.package_deduction_inr or 0)
            + float(inv.adjustment_inr or 0),
        )
    if updates.get("status") == "GENERATED" and inv.status == ClientInvoiceStatus.DRAFT:
        inv.status = ClientInvoiceStatus.GENERATED
    db.flush()
    return inv


def admin_summary(db: Session) -> dict:
    rows = db.scalars(select(ClientInvoice)).all()
    today = date.today()
    month_prefix = today.strftime("%b %Y")
    total_outstanding = 0.0
    overdue_count = 0
    disputed_count = 0
    paid_this_month = 0
    draft_count = 0
    sent_unpaid = 0

    for inv in rows:
        balance = float(inv.total_inr) - float(inv.amount_paid_inr or 0)
        if inv.status == ClientInvoiceStatus.DRAFT:
            draft_count += 1
        if inv.status == ClientInvoiceStatus.DISPUTED:
            disputed_count += 1
        if inv.status == ClientInvoiceStatus.PAID or balance <= 0:
            if inv.billing_month == month_prefix or (
                inv.updated_at and inv.updated_at.strftime("%b %Y") == month_prefix
            ):
                paid_this_month += 1
        elif balance > 0:
            total_outstanding += balance
            if _invoice_is_overdue(inv, balance):
                overdue_count += 1
            if inv.status in (ClientInvoiceStatus.SENT, ClientInvoiceStatus.PARTIALLY_PAID, ClientInvoiceStatus.GENERATED):
                sent_unpaid += 1

    open_disputes = (
        db.scalar(
            select(func.count())
            .select_from(BillingDispute)
            .where(
                BillingDispute.status.in_(
                    [BillingDisputeStatus.OPEN, BillingDisputeStatus.UNDER_REVIEW]
                )
            )
        )
        or 0
    )

    return {
        "totalOutstandingInr": round(total_outstanding, 2),
        "overdueCount": overdue_count,
        "disputedCount": disputed_count,
        "openDisputesCount": open_disputes,
        "paidThisMonthCount": paid_this_month,
        "draftCount": draft_count,
        "sentUnpaidCount": sent_unpaid,
        "invoiceCount": len(rows),
    }


BILLING_PROOF_DIR = Path("uploads/billing")
MAX_PROOF_BYTES = 5 * 1024 * 1024
ALLOWED_PROOF_MIME = frozenset(
    {"image/jpeg", "image/png", "image/webp", "application/pdf"}
)


async def _save_payment_proof(file: UploadFile, payment_id: int) -> tuple[str, str]:
    if not file.filename:
        raise ValueError("Proof file is required")
    content = await file.read()
    if len(content) > MAX_PROOF_BYTES:
        raise ValueError("Proof file must be 5 MB or smaller")
    mime = file.content_type or "application/octet-stream"
    if mime not in ALLOWED_PROOF_MIME:
        raise ValueError("Proof must be JPEG, PNG, WebP, or PDF")
    BILLING_PROOF_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name.replace("..", "")
    dest_name = f"{payment_id}_{secrets.token_hex(4)}_{safe_name}"
    dest = BILLING_PROOF_DIR / dest_name
    dest.write_bytes(content)
    return str(dest), safe_name


async def submit_payment_claim(
    db: Session,
    user: User,
    invoice_id: int,
    amount_inr: float,
    method: str,
    reference: Optional[str],
    notes: Optional[str],
    proof_file: Optional[UploadFile],
) -> ClientPayment:
    inv_detail = get_invoice_detail(db, user, invoice_id)
    balance = float(inv_detail.get("balanceInr") or 0)
    if amount_inr <= 0:
        raise ValueError("Amount must be greater than zero")
    if amount_inr > balance + 0.01:
        raise ValueError("Amount exceeds invoice balance")
    inv = db.get(ClientInvoice, invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    payment = ClientPayment(
        client_invoice_id=inv.id,
        amount_inr=amount_inr,
        method=PaymentMethod(method),
        reference=reference,
        notes=notes,
        submitted_by_user_id=user.id,
        payment_status=ClientPaymentStatus.PENDING_REVIEW,
    )
    db.add(payment)
    db.flush()
    if proof_file and proof_file.filename:
        path, name = await _save_payment_proof(proof_file, payment.id)
        payment.proof_file_path = path
        payment.proof_file_name = name
    notification_service.create_notification(
        db,
        user_id=user.id,
        title="Payment submitted",
        body=f"We received your payment claim for {inv.invoice_number}. Finance will confirm shortly.",
        entity_type="client_invoice",
        entity_id=inv.id,
    )
    db.flush()
    return payment


def confirm_payment_claim(db: Session, payment_id: int, admin_user_id: int) -> ClientInvoice:
    payment = db.get(ClientPayment, payment_id)
    if not payment or payment.payment_status != ClientPaymentStatus.PENDING_REVIEW:
        raise ValueError("Payment claim not found")
    inv = db.get(ClientInvoice, payment.client_invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    payment.payment_status = ClientPaymentStatus.CONFIRMED
    payment.confirmed_by_user_id = admin_user_id
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.recorded_by_user_id = admin_user_id
    inv.amount_paid_inr = float(inv.amount_paid_inr or 0) + float(payment.amount_inr)
    balance = float(inv.total_inr) - float(inv.amount_paid_inr)
    if balance <= 0:
        inv.status = ClientInvoiceStatus.PAID
    elif float(inv.amount_paid_inr) > 0:
        inv.status = ClientInvoiceStatus.PARTIALLY_PAID
    notification_service.create_notification(
        db,
        user_id=inv.parent_user_id,
        title="Payment confirmed",
        body=f"₹{int(payment.amount_inr):,} confirmed for {inv.invoice_number}",
        entity_type="client_invoice",
        entity_id=inv.id,
    )
    db.flush()
    return inv


def reject_payment_claim(db: Session, payment_id: int, admin_user_id: int, note: str) -> ClientPayment:
    payment = db.get(ClientPayment, payment_id)
    if not payment or payment.payment_status != ClientPaymentStatus.PENDING_REVIEW:
        raise ValueError("Payment claim not found")
    payment.payment_status = ClientPaymentStatus.REJECTED
    payment.confirmed_by_user_id = admin_user_id
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.rejection_note = note.strip()
    inv = db.get(ClientInvoice, payment.client_invoice_id)
    if inv:
        notification_service.create_notification(
            db,
            user_id=inv.parent_user_id,
            title="Payment not confirmed",
            body=f"Your payment claim for {inv.invoice_number} was not accepted. {payment.rejection_note}",
            entity_type="client_invoice",
            entity_id=inv.id,
        )
    db.flush()
    return payment


def payment_proof_download(db: Session, user: User, payment_id: int, *, admin: bool = False):
    from fastapi.responses import FileResponse

    payment = db.get(ClientPayment, payment_id)
    if not payment or not payment.proof_file_path:
        raise ValueError("Proof not found")
    inv = db.get(ClientInvoice, payment.client_invoice_id)
    if not inv:
        raise ValueError("Proof not found")
    if not admin and inv.parent_user_id != user.id:
        raise ValueError("Proof not found")
    path = Path(payment.proof_file_path)
    if not path.is_file():
        raise ValueError("Proof file missing")
    return FileResponse(path, filename=payment.proof_file_name or path.name)


def client_invoice_pdf_bytes(inv_detail: dict) -> bytes:
    """Build a simple client invoice PDF from get_invoice_detail payload."""
    import io

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InvTitle", parent=styles["Title"], fontSize=16, spaceAfter=6)
    meta_style = ParagraphStyle("InvMeta", parent=styles["Normal"], fontSize=10, textColor=colors.grey)

    story = [
        Paragraph(inv_detail.get("invoiceNumber", "Invoice"), title_style),
        Paragraph(
            f"{inv_detail.get('childName', '')} · {inv_detail.get('caseId', '')} · {inv_detail.get('month', '')}",
            meta_style,
        ),
        Paragraph(
            f"Status: {inv_detail.get('status', '')} · Due: {inv_detail.get('dueDate') or '—'} · "
            f"Balance: ₹{inv_detail.get('balanceInr', 0):,.0f}",
            meta_style,
        ),
        Spacer(1, 12),
    ]

    table_data = [["Date", "Therapist", "Service", "Status", "Amount (₹)"]]
    for line in inv_detail.get("lines") or []:
        table_data.append(
            [
                line.get("sessionDate", ""),
                line.get("therapistName", ""),
                line.get("serviceLabel", ""),
                line.get("sessionStatus", ""),
                f"{line.get('amountInr', 0):,.0f}",
            ]
        )
    table_data.append(["", "", "", "Total", f"{inv_detail.get('totalInr', 0):,.0f}"])
    table_data.append(["", "", "", "Paid", f"{inv_detail.get('amountPaidInr', 0):,.0f}"])

    tbl = Table(table_data, colWidths=[70, 100, 120, 70, 70])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("ALIGN", (4, 1), (4, -1), "RIGHT"),
            ]
        )
    )
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()
