from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
import secrets
import shutil

from fastapi import BackgroundTasks, UploadFile

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.case import BillingType, Case, ClientBillingMode
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
from app.services import billing_composer_service, notification_service, parent_service, product_billing_rule_service
from app.services.email.service import enqueue_parent_invoice_email, parent_invoice_ready_email


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
    line_ids: Optional[list[int]] = None,
) -> dict:
    inv = db.get(ClientInvoice, invoice_id)
    if not inv or inv.parent_user_id != user.id:
        raise ValueError("Invoice not found")

    if line_ids is not None:
        target_line_ids: list[Optional[int]] = [None] if len(line_ids) == 0 else list(dict.fromkeys(line_ids))
    elif line_id is not None:
        target_line_ids = [line_id]
    else:
        target_line_ids = [None]

    for lid in target_line_ids:
        if lid is None:
            continue
        line = db.get(ClientInvoiceLine, lid)
        if not line or line.client_invoice_id != inv.id:
            raise ValueError("Invalid line")

    created: list[BillingDispute] = []
    for lid in target_line_ids:
        dispute = BillingDispute(
            client_invoice_id=inv.id,
            client_invoice_line_id=lid,
            parent_user_id=user.id,
            reason_code=reason_code,
            message=message,
            status=BillingDisputeStatus.OPEN,
        )
        db.add(dispute)
        created.append(dispute)

    inv.status = ClientInvoiceStatus.DISPUTED
    db.flush()

    case = db.get(Case, inv.case_id)
    if case and case.case_manager_user_id:
        session_note = ""
        if len(target_line_ids) > 1 or (len(target_line_ids) == 1 and target_line_ids[0] is not None):
            session_note = f" ({len(target_line_ids)} session{'s' if len(target_line_ids) != 1 else ''})"
        notification_service.create_notification(
            db,
            user_id=case.case_manager_user_id,
            title="Invoice dispute raised",
            body=f"{inv.invoice_number}{session_note}: {message[:200]}",
            entity_type="client_invoice",
            entity_id=inv.id,
        )

    first = created[0]
    return {
        "id": first.id,
        "ids": [d.id for d in created],
        "count": len(created),
        "status": first.status.value.lower(),
    }


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


def notify_parent_invoice_issued(
    db: Session,
    invoice_id: int,
    background_tasks: BackgroundTasks | None = None,
    *,
    resend: bool = False,
) -> dict:
    """Email + in-app notice. Idempotent unless resend=True. Sets sent_at and promotes GENERATED → SENT."""
    inv = db.get(ClientInvoice, invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    parent = db.get(User, inv.parent_user_id)
    if not parent:
        raise ValueError("Parent not found")
    if inv.sent_at and not resend:
        return {"status": "already_sent", "sent_at": inv.sent_at.isoformat()}

    if not inv.payment_policy_snapshot:
        from app.services.billing_composer_service import DEFAULT_PAYMENT_POLICY

        inv.payment_policy_snapshot = DEFAULT_PAYMENT_POLICY

    case = db.get(Case, inv.case_id)
    child_name = case.child.full_name if case and case.child else "Your child"
    balance = float(inv.total_inr) - float(inv.amount_paid_inr or 0)
    is_overdue = _invoice_is_overdue(inv, balance)
    due_str = inv.due_date.strftime("%d %b %Y") if inv.due_date else None
    url = f"{settings.frontend_url.rstrip('/')}/parent/billing"

    email_kwargs = dict(
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
    if background_tasks is not None:
        enqueue_parent_invoice_email(background_tasks, db, **email_kwargs)
    else:
        parent_invoice_ready_email(**email_kwargs)
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
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[str] = None,
    invoice_type: Optional[str] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
    claims_pending: bool = False,
) -> list[dict]:
    from datetime import date as date_type, datetime, timedelta, timezone

    stmt = (
        select(ClientInvoice)
        .options(selectinload(ClientInvoice.payments))
        .order_by(ClientInvoice.created_at.desc())
    )
    if month:
        stmt = stmt.where(ClientInvoice.billing_month == month)
    elif year:
        stmt = stmt.where(ClientInvoice.billing_month.contains(str(year)))
    if case_id:
        stmt = stmt.where(ClientInvoice.case_id == case_id)
    if invoice_type:
        try:
            stmt = stmt.where(ClientInvoice.invoice_type == ClientInvoiceType(invoice_type))
        except ValueError:
            pass
    if module:
        stmt = stmt.where(ClientInvoice.product_module == module)
    if date_from:
        start = datetime.combine(date_type.fromisoformat(date_from), datetime.min.time()).replace(tzinfo=timezone.utc)
        stmt = stmt.where(ClientInvoice.created_at >= start)
    if date_to:
        end_day = date_type.fromisoformat(date_to) + timedelta(days=1)
        end = datetime.combine(end_day, datetime.min.time()).replace(tzinfo=timezone.utc)
        stmt = stmt.where(ClientInvoice.created_at < end)

    filter_overdue = status and status.upper() == "OVERDUE"
    if status and not filter_overdue:
        try:
            stmt = stmt.where(ClientInvoice.status == ClientInvoiceStatus(status))
        except ValueError:
            pass

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
        item["payments"] = [
            {
                "id": p.id,
                "amountInr": float(p.amount_inr),
                "paymentStatus": p.payment_status.value.lower(),
            }
            for p in (inv.payments or [])
        ]
        if claims_pending:
            if not any(p.payment_status == ClientPaymentStatus.PENDING_REVIEW for p in (inv.payments or [])):
                continue
        if filter_overdue:
            balance = float(inv.total_inr) - float(inv.amount_paid_inr or 0)
            if not _invoice_is_overdue(inv, balance):
                continue
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


def admin_invoice_filter_options(db: Session) -> dict:
    months = [
        m
        for (m,) in db.execute(
            select(ClientInvoice.billing_month)
            .distinct()
            .order_by(ClientInvoice.billing_month.desc())
        ).all()
        if m
    ]
    years = sorted({int(m.split()[-1]) for m in months if m and m.split()[-1].isdigit()}, reverse=True)
    service_rows = db.scalars(select(Case.product_module).distinct().order_by(Case.product_module)).all()
    services = sorted({s for s in service_rows if s})
    return {
        "billingMonths": months,
        "years": years,
        "statuses": [s.value for s in ClientInvoiceStatus] + ["OVERDUE"],
        "invoiceTypes": [t.value for t in ClientInvoiceType],
        "services": services,
        "composerQueues": list(billing_composer_service.COMPOSER_QUEUES),
    }


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
            "organisationId": inv.organisation_id,
            "purchaseOrderRef": inv.purchase_order_ref,
            "contractRef": inv.contract_ref,
            "lines": [_serialize_line(line) for line in lines],
            "paymentPolicySnapshot": inv.payment_policy_snapshot,
            "gatewayEnabled": bool(getattr(inv, "gateway_enabled", False)),
            "gatewayPaymentUrl": getattr(inv, "gateway_payment_url", None),
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
    try:
        preview = billing_composer_service.get_composer_preview(
            db, case_id=inv.case_id, billing_month=inv.billing_month or ""
        )
        ov = preview.get("overview") or {}
        detail["billingPreview"] = {
            "sessionsCompleted": ov.get("sessionsCompleted"),
            "sessionsBillable": ov.get("sessionsBillable"),
            "leavesTotal": ov.get("leavesTotal"),
            "therapistPayoutTotalInr": ov.get("therapistPayoutTotal"),
            "estimatedMarginInr": ov.get("estimatedMargin"),
            "subtotalInr": ov.get("subtotal"),
            "taxAmountInr": ov.get("taxAmount"),
            "suggestedTotalInr": ov.get("total"),
        }
    except ValueError:
        detail["billingPreview"] = None
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
                line_item_type=ln.get("line_item_type"),
                gst_rate_percent=ln.get("gst_rate_percent"),
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
    if "payment_policy_snapshot" in updates:
        inv.payment_policy_snapshot = updates["payment_policy_snapshot"]
    if "gateway_enabled" in updates and updates["gateway_enabled"] is not None:
        inv.gateway_enabled = bool(updates["gateway_enabled"])
    if "gateway_payment_url" in updates:
        inv.gateway_payment_url = updates["gateway_payment_url"]
    db.flush()
    return inv


def _require_draft_invoice(inv: ClientInvoice) -> None:
    if inv.status != ClientInvoiceStatus.DRAFT:
        raise ValueError("Only draft invoices can be edited")


def _normalize_client_invoice_line(line: ClientInvoiceLine) -> None:
    """Derive unit rate, taxable base, GST, and line total from qty × rate + tax."""
    qty = float(line.quantity or 1)
    if qty <= 0:
        qty = 1.0
        line.quantity = qty

    gst_pct = float(line.gst_rate_percent or 0)
    rate = line.unit_rate_inr

    if rate is None and line.amount_inr and qty:
        total = float(line.amount_inr)
        if gst_pct > 0:
            taxable_unit = total / (1 + gst_pct / 100) / qty
            line.unit_rate_inr = round(taxable_unit, 2)
            rate = line.unit_rate_inr
        else:
            line.unit_rate_inr = round(total / qty, 2)
            rate = line.unit_rate_inr

    if rate is not None:
        taxable = round(qty * float(rate), 2)
        line.taxable_amount_inr = taxable
        if gst_pct > 0:
            line.gst_amount_inr = round(taxable * gst_pct / 100, 2)
            line.amount_inr = round(taxable + float(line.gst_amount_inr), 2)
        else:
            line.gst_amount_inr = 0
            line.amount_inr = taxable
    elif line.amount_inr is not None:
        taxable = float(line.taxable_amount_inr if line.taxable_amount_inr is not None else line.amount_inr)
        line.taxable_amount_inr = round(taxable, 2)
        if gst_pct > 0:
            line.gst_amount_inr = round(taxable * gst_pct / 100, 2)
            line.amount_inr = round(taxable + float(line.gst_amount_inr), 2)
        else:
            line.gst_amount_inr = 0
            line.amount_inr = round(taxable, 2)


def _serialize_line(line: ClientInvoiceLine) -> dict:
    return {
        "id": line.id,
        "sessionDate": line.session_date.isoformat(),
        "therapistName": line.therapist_name,
        "serviceLabel": line.service_label,
        "sessionStatus": line.session_status,
        "amountInr": float(line.amount_inr),
        "lineItemType": line.line_item_type or "SESSION_CHARGE",
        "quantity": float(line.quantity) if line.quantity is not None else 1,
        "unitRateInr": float(line.unit_rate_inr) if line.unit_rate_inr is not None else None,
        "packageDeducted": line.package_deducted,
        "parentSummary": line.parent_summary,
        "sessionId": line.session_id,
        "dailyLogId": line.daily_log_id,
        "gstRatePercent": float(line.gst_rate_percent) if line.gst_rate_percent is not None else None,
        "gstAmountInr": float(line.gst_amount_inr) if line.gst_amount_inr is not None else None,
        "hsnSacCode": line.hsn_sac_code,
        "taxableAmountInr": float(line.taxable_amount_inr) if line.taxable_amount_inr is not None else None,
        "billingLedgerId": line.billing_ledger_id,
        "therapistUserId": line.therapist_user_id,
        "financeNote": line.finance_note,
        "sortOrder": line.sort_order,
    }


def recalculate_client_invoice(db: Session, invoice_id: int) -> ClientInvoice:
    inv = db.scalar(
        select(ClientInvoice)
        .where(ClientInvoice.id == invoice_id)
        .options(selectinload(ClientInvoice.lines))
    )
    if not inv:
        raise ValueError("Invoice not found")
    subtotal = 0.0
    tax = 0.0
    for line in inv.lines or []:
        _normalize_client_invoice_line(line)
        if line.line_item_type == "DISCOUNT":
            continue
        taxable = float(line.taxable_amount_inr if line.taxable_amount_inr is not None else line.amount_inr)
        if line.line_item_type != "TAX":
            subtotal += taxable
        tax += float(line.gst_amount_inr or 0)
    inv.subtotal_inr = round(subtotal, 2)
    inv.tax_inr = round(tax, 2)
    inv.total_inr = max(
        0,
        round(
            float(inv.subtotal_inr)
            + float(inv.tax_inr)
            - float(inv.discount_inr or 0)
            - float(inv.package_deduction_inr or 0)
            + float(inv.adjustment_inr or 0),
            2,
        ),
    )
    db.flush()
    return inv


def admin_add_invoice_line(db: Session, invoice_id: int, data: dict) -> ClientInvoiceLine:
    inv = db.get(ClientInvoice, invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    _require_draft_invoice(inv)
    sort = max((ln.sort_order for ln in (inv.lines or [])), default=-1) + 1
    qty = float(data.get("quantity") or 1)
    rate = data.get("unit_rate_inr")
    amount = float(data["amount_inr"])
    if rate is not None:
        amount = round(qty * float(rate), 2)
    line = ClientInvoiceLine(
        client_invoice_id=invoice_id,
        session_id=data.get("session_id"),
        daily_log_id=data.get("daily_log_id"),
        session_date=data["session_date"],
        therapist_name=data["therapist_name"],
        service_label=data["service_label"],
        session_status=data.get("session_status", "COMPLETED"),
        amount_inr=amount,
        line_item_type=data.get("line_item_type") or "SESSION_CHARGE",
        quantity=qty,
        unit_rate_inr=rate,
        gst_rate_percent=data.get("gst_rate_percent"),
        gst_amount_inr=data.get("gst_amount_inr"),
        taxable_amount_inr=data.get("taxable_amount_inr") or amount,
        billing_ledger_id=data.get("billing_ledger_id"),
        therapist_user_id=data.get("therapist_user_id"),
        finance_note=data.get("finance_note"),
        parent_summary=data.get("parent_summary"),
        hsn_sac_code=data.get("hsn_sac_code"),
        sort_order=sort,
    )
    db.add(line)
    db.flush()
    _normalize_client_invoice_line(line)
    db.flush()
    recalculate_client_invoice(db, invoice_id)
    return line


def admin_patch_invoice_line(
    db: Session, invoice_id: int, line_id: int, data: dict
) -> ClientInvoiceLine:
    inv = db.get(ClientInvoice, invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    _require_draft_invoice(inv)
    line = db.get(ClientInvoiceLine, line_id)
    if not line or line.client_invoice_id != invoice_id:
        raise ValueError("Line not found")
    before = _serialize_line(line)
    for key, attr in (
        ("session_date", "session_date"),
        ("therapist_name", "therapist_name"),
        ("service_label", "service_label"),
        ("session_status", "session_status"),
        ("amount_inr", "amount_inr"),
        ("line_item_type", "line_item_type"),
        ("quantity", "quantity"),
        ("unit_rate_inr", "unit_rate_inr"),
        ("gst_rate_percent", "gst_rate_percent"),
        ("gst_amount_inr", "gst_amount_inr"),
        ("taxable_amount_inr", "taxable_amount_inr"),
        ("finance_note", "finance_note"),
        ("parent_summary", "parent_summary"),
        ("hsn_sac_code", "hsn_sac_code"),
    ):
        if key in data and data[key] is not None:
            setattr(line, attr, data[key])
    _normalize_client_invoice_line(line)
    db.flush()
    recalculate_client_invoice(db, invoice_id)
    line._audit_before = before  # noqa: SLF001 — consumed by API layer
    return line


def admin_delete_invoice_line(db: Session, invoice_id: int, line_id: int) -> None:
    inv = db.get(ClientInvoice, invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    _require_draft_invoice(inv)
    line = db.get(ClientInvoiceLine, line_id)
    if not line or line.client_invoice_id != invoice_id:
        raise ValueError("Line not found")
    db.delete(line)
    db.flush()
    recalculate_client_invoice(db, invoice_id)


def save_case_billing_preferences(db: Session, case_id: int, data: dict) -> None:
    from app.models.case_billing_preference import CaseBillingPreference

    pref = db.scalar(select(CaseBillingPreference).where(CaseBillingPreference.case_id == case_id))
    if not pref:
        pref = CaseBillingPreference(case_id=case_id)
        db.add(pref)
    for key in (
        "invoice_type",
        "gst_applicable",
        "gst_rate_percent",
        "gateway_enabled",
        "due_date_offset_days",
        "payment_policy_template",
    ):
        if key in data and data[key] is not None:
            setattr(pref, key, data[key])
    db.flush()


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
    from app.storage.object_io import put_stored_bytes

    safe_name = Path(file.filename).name.replace("..", "")
    storage_key, _provider = put_stored_bytes(
        "billing-proofs",
        f"payment_{payment_id}",
        filename=safe_name,
        data=content,
        content_type=mime,
    )
    return storage_key, safe_name


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
    _activate_packages_for_invoice(db, inv)
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
    from app.storage.object_io import stored_file_response

    payment = db.get(ClientPayment, payment_id)
    if not payment or not payment.proof_file_path:
        raise ValueError("Proof not found")
    inv = db.get(ClientInvoice, payment.client_invoice_id)
    if not inv:
        raise ValueError("Proof not found")
    if not admin and inv.parent_user_id != user.id:
        raise ValueError("Proof not found")
    return stored_file_response(
        payment.proof_file_path,
        filename=payment.proof_file_name or "proof",
        media_type="application/octet-stream",
    )


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


def _activate_packages_for_invoice(db: Session, inv: ClientInvoice) -> None:
    if inv.status not in (ClientInvoiceStatus.PAID, ClientInvoiceStatus.PARTIALLY_PAID):
        return
    packages = db.scalars(
        select(CarePackage).where(
            CarePackage.client_invoice_id == inv.id,
            CarePackage.status == CarePackageStatus.PENDING_PAYMENT,
        )
    ).all()
    for pkg in packages:
        pkg.status = CarePackageStatus.ACTIVE
        if not pkg.valid_from:
            pkg.valid_from = date.today()
    db.flush()


def admin_list_packages(db: Session, *, case_id: Optional[int] = None) -> list[dict]:
    stmt = select(CarePackage).order_by(CarePackage.created_at.desc())
    if case_id:
        stmt = stmt.where(CarePackage.case_id == case_id)
    rows = db.scalars(stmt).all()
    return [
        {
            "id": p.id,
            "caseId": p.case_id,
            "parentUserId": p.parent_user_id,
            "name": p.name,
            "totalSessions": p.total_sessions,
            "usedSessions": p.used_sessions,
            "remainingSessions": max(0, p.total_sessions - p.used_sessions),
            "validityEnd": p.validity_end.isoformat() if p.validity_end else None,
            "validFrom": p.valid_from.isoformat() if p.valid_from else None,
            "status": p.status.value,
            "serviceLabel": p.service_label,
            "amountInr": float(p.amount_inr) if p.amount_inr is not None else None,
            "productBillingRuleId": p.product_billing_rule_id,
            "clientInvoiceId": p.client_invoice_id,
        }
        for p in rows
    ]


def admin_create_package(db: Session, data: dict) -> dict:
    case = db.get(Case, data["case_id"])
    if not case:
        raise ValueError("Case not found")
    pkg = CarePackage(
        case_id=data["case_id"],
        parent_user_id=data["parent_user_id"],
        name=data["name"],
        total_sessions=data["total_sessions"],
        validity_end=data.get("validity_end"),
        service_label=data.get("service_label") or case.service_type,
        status=CarePackageStatus.PENDING_PAYMENT,
        product_billing_rule_id=data.get("product_billing_rule_id"),
        amount_inr=data.get("amount_inr"),
    )
    db.add(pkg)
    db.flush()
    return {
        "id": pkg.id,
        "caseId": pkg.case_id,
        "parentUserId": pkg.parent_user_id,
        "name": pkg.name,
        "totalSessions": pkg.total_sessions,
        "usedSessions": pkg.used_sessions,
        "remainingSessions": pkg.total_sessions,
        "status": pkg.status.value,
    }


def admin_update_package(db: Session, package_id: int, updates: dict) -> dict:
    pkg = db.get(CarePackage, package_id)
    if not pkg:
        raise ValueError("Package not found")
    for key, value in updates.items():
        if value is None:
            continue
        if key == "status":
            pkg.status = CarePackageStatus(value)
        else:
            setattr(pkg, key, value)
    db.flush()
    rows = admin_list_packages(db, case_id=pkg.case_id)
    return next((r for r in rows if r["id"] == package_id), rows[0] if rows else {})


def create_draft_from_case_defaults(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    admin_user_id: int,
) -> dict:
    """Create a DRAFT client invoice with lines prefilled from case billing settings."""
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    ym = billing_composer_service.normalize_billing_month(billing_month)
    warnings: list[str] = []

    from app.models.ledger_billing import ProductBillingModel

    rule = None
    if case.product_billing_rule_id:
        rule = product_billing_rule_service.get_rule(db, case.product_billing_rule_id)

    invoice_type = "POSTPAID"
    if case.client_billing_mode == ClientBillingMode.PREPAID or case.billing_type == BillingType.PACKAGE:
        invoice_type = "PREPAID"
    elif rule and rule.billing_model == ProductBillingModel.MONTHLY_FIXED:
        invoice_type = "MONTHLY_FIXED"

    lines: list[dict] = []
    today = date.today()
    therapist_name = "—"
    service_label = case.service_type or "Service"
    gst_rate = float(rule.gst_rate_percent or 0) if rule else 0.0

    amount = 0.0
    if case.package_amount_inr and float(case.package_amount_inr) > 0:
        amount = float(case.package_amount_inr)
        line_type = "PACKAGE_CHARGE"
    elif case.client_rate_per_session_inr and float(case.client_rate_per_session_inr) > 0:
        amount = float(case.client_rate_per_session_inr)
        line_type = "SESSION_CHARGE"
    else:
        warnings.append("no_default_rule")
        amount = 0.01
        line_type = "MANUAL_FEE"

    if amount > 0:
        lines.append(
            {
                "session_date": today,
                "therapist_name": therapist_name,
                "service_label": service_label,
                "session_status": "COMPLETED",
                "amount_inr": amount,
                "line_item_type": line_type,
                "gst_rate_percent": gst_rate if gst_rate else None,
            }
        )

    inv = admin_create_invoice(
        db,
        case_id=case_id,
        invoice_type=invoice_type,
        billing_month=ym,
        due_date=None,
        lines=lines,
        notes=case.billing_notes,
        discount_inr=0,
        admin_user_id=admin_user_id,
    )
    detail = admin_get_invoice_detail(db, inv.id)
    detail["warnings"] = warnings
    return detail


def case_billing_summary(db: Session, case_id: int) -> dict:
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    last_inv = db.scalar(
        select(ClientInvoice)
        .where(ClientInvoice.case_id == case_id)
        .order_by(ClientInvoice.id.desc())
        .limit(1)
    )
    open_balance = 0.0
    if last_inv and last_inv.status in (
        ClientInvoiceStatus.SENT,
        ClientInvoiceStatus.PARTIALLY_PAID,
        ClientInvoiceStatus.OVERDUE,
        ClientInvoiceStatus.GENERATED,
    ):
        open_balance = max(0, float(last_inv.total_inr or 0) - float(last_inv.amount_paid_inr or 0))

    rule_name = None
    if case.product_billing_rule_id:
        rule = product_billing_rule_service.get_rule(db, case.product_billing_rule_id)
        rule_name = rule.product_name if rule else None

    return {
        "caseId": case_id,
        "billingType": case.billing_type.value if case.billing_type else None,
        "clientBillingMode": case.client_billing_mode.value if case.client_billing_mode else None,
        "clientRatePerSessionInr": float(case.client_rate_per_session_inr) if case.client_rate_per_session_inr else None,
        "packageAmountInr": float(case.package_amount_inr) if case.package_amount_inr else None,
        "productBillingRuleName": rule_name,
        "lastInvoice": {
            "id": last_inv.id,
            "status": last_inv.status.value,
            "billingMonth": last_inv.billing_month,
            "totalInr": float(last_inv.total_inr or 0),
        }
        if last_inv
        else None,
        "openBalanceInr": open_balance,
    }


def admin_list_disputes(db: Session) -> list[dict]:
    rows = db.scalars(
        select(BillingDispute).order_by(BillingDispute.created_at.desc()).limit(200)
    ).all()
    return [
        {
            "id": d.id,
            "clientInvoiceId": d.client_invoice_id,
            "lineId": d.client_invoice_line_id,
            "parentUserId": d.parent_user_id,
            "reasonCode": d.reason_code,
            "message": d.message,
            "status": d.status.value,
            "createdAt": d.created_at.isoformat() if d.created_at else None,
        }
        for d in rows
    ]
