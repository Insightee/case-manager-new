from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.ledger_billing import (
    BillableStatus,
    BillingLedger,
    LedgerDisputeStatus,
    LedgerEventType,
    LedgerSourceType,
    ProductBillingModel,
    ProductBillingRule,
)
from app.models.parent import ParentGuardian, parent_child_link
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services import product_billing_rule_service


def _ledger_month(d: date) -> str:
    return d.strftime("%Y-%m")


def _parent_for_case(db: Session, case: Case) -> int | None:
    row = db.execute(
        select(ParentGuardian.user_id)
        .join(parent_child_link, parent_child_link.c.parent_id == ParentGuardian.id)
        .where(parent_child_link.c.child_id == case.child_id)
        .limit(1)
    ).first()
    return row[0] if row else None


def _resolve_rule(db: Session, case: Case) -> ProductBillingRule | None:
    if case.product_billing_rule_id:
        return product_billing_rule_service.get_rule(db, case.product_billing_rule_id)
    stmt = (
        select(ProductBillingRule)
        .where(
            ProductBillingRule.product_module == case.product_module,
            ProductBillingRule.active.is_(True),
        )
        .order_by(ProductBillingRule.id)
    )
    return db.scalars(stmt).first()


def _rate_for_case(case: Case, rule: ProductBillingRule | None) -> float:
    if case.client_rate_per_session_inr is not None:
        return float(case.client_rate_per_session_inr)
    if rule and rule.default_rate_inr is not None:
        return float(rule.default_rate_inr)
    return 0.0


def _amounts(amount: float, rule: ProductBillingRule | None) -> tuple[float, float | None, float | None, str | None]:
    gst_rate = float(rule.gst_rate_percent) if rule and rule.gst_applicable and rule.gst_rate_percent else None
    gst_amount = round(amount * gst_rate / 100, 2) if gst_rate else None
    total = round(amount + (gst_amount or 0), 2)
    hsn = rule.hsn_sac_code if rule else None
    return amount, gst_rate, gst_amount, hsn


def _existing_ledger(
    db: Session,
    *,
    source_type: LedgerSourceType,
    source_id: int,
) -> BillingLedger | None:
    return db.scalars(
        select(BillingLedger).where(
            BillingLedger.source_type == source_type,
            BillingLedger.source_id == source_id,
        )
    ).first()


def upsert_from_daily_log_approved(db: Session, log: DailyLog) -> BillingLedger | None:
    session = log.session
    if not session:
        return None
    return upsert_from_session_event(
        db,
        session,
        event_type=LedgerEventType.SESSION_COMPLETED,
        billable_default=BillableStatus.BILLABLE,
        daily_log_id=log.id,
        source_type=LedgerSourceType.DAILY_LOG,
        source_id=log.id,
    )


def upsert_from_session_event(
    db: Session,
    session: TherapySession,
    *,
    event_type: LedgerEventType,
    billable_default: BillableStatus,
    daily_log_id: Optional[int] = None,
    source_type: LedgerSourceType = LedgerSourceType.SESSION,
    source_id: Optional[int] = None,
) -> BillingLedger | None:
    case = session.case or db.get(Case, session.case_id)
    if not case:
        return None
    rule = _resolve_rule(db, case)
    if rule and rule.billing_model == ProductBillingModel.MONTHLY_FIXED:
        return None

    sid = source_id or session.id
    existing = _existing_ledger(db, source_type=source_type, source_id=sid)
    if existing and existing.billable_status == BillableStatus.INVOICED:
        return existing

    billable = billable_default
    if event_type == LedgerEventType.CLIENT_NO_SHOW:
        billable = (
            BillableStatus.BILLABLE
            if rule and rule.client_no_show_billable
            else BillableStatus.NON_BILLABLE
        )
    elif event_type == LedgerEventType.THERAPIST_CANCEL:
        billable = (
            BillableStatus.BILLABLE
            if rule and rule.therapist_cancel_billable
            else BillableStatus.NON_BILLABLE
        )
    elif event_type == LedgerEventType.SESSION_CANCELLED:
        billable = BillableStatus.NON_BILLABLE

    rate = _rate_for_case(case, rule)
    amount, gst_rate, gst_amount, hsn = _amounts(rate, rule)
    total = amount + (gst_amount or 0)
    parent_id = _parent_for_case(db, case)

    if existing:
        existing.event_type = event_type
        existing.billable_status = billable
        existing.rate_inr = rate
        existing.amount_inr = amount
        existing.gst_rate_percent = gst_rate
        existing.gst_amount_inr = gst_amount
        existing.hsn_sac_code = hsn
        existing.total_inr = total
        existing.therapist_user_id = session.therapist_user_id
        existing.daily_log_id = daily_log_id
        db.flush()
        return existing

    row = BillingLedger(
        case_id=case.id,
        parent_user_id=parent_id,
        therapist_user_id=session.therapist_user_id,
        product_billing_rule_id=rule.id if rule else None,
        source_type=source_type,
        source_id=sid,
        session_id=session.id,
        daily_log_id=daily_log_id,
        ledger_month=_ledger_month(session.scheduled_date),
        event_date=session.scheduled_date,
        event_type=event_type,
        billable_status=billable,
        quantity=1,
        rate_inr=rate,
        amount_inr=amount,
        gst_rate_percent=gst_rate,
        gst_amount_inr=gst_amount,
        hsn_sac_code=hsn,
        total_inr=total,
        dispute_status=LedgerDisputeStatus.NONE,
    )
    db.add(row)
    db.flush()
    return row


def sync_session_status(db: Session, session: TherapySession) -> BillingLedger | None:
    status = session.status
    if status == SessionStatus.COMPLETED:
        log = session.daily_log
        if log and log.approval_status == LogApprovalStatus.APPROVED:
            return upsert_from_daily_log_approved(db, log)
        return upsert_from_session_event(
            db,
            session,
            event_type=LedgerEventType.SESSION_COMPLETED,
            billable_default=BillableStatus.PENDING_REVIEW,
        )
    if status == SessionStatus.NO_SHOW or status == SessionStatus.CLIENT_ABSENT:
        return upsert_from_session_event(
            db,
            session,
            event_type=LedgerEventType.CLIENT_NO_SHOW,
            billable_default=BillableStatus.PENDING_REVIEW,
        )
    if status == SessionStatus.CANCELLED:
        return upsert_from_session_event(
            db,
            session,
            event_type=LedgerEventType.THERAPIST_CANCEL,
            billable_default=BillableStatus.PENDING_REVIEW,
        )
    return None


def list_ledger(
    db: Session,
    *,
    ledger_month: Optional[str] = None,
    case_id: Optional[int] = None,
    billable_status: Optional[str] = None,
) -> list[dict]:
    stmt = select(BillingLedger).options(selectinload(BillingLedger.case)).order_by(
        BillingLedger.event_date.desc(), BillingLedger.id.desc()
    )
    if ledger_month:
        stmt = stmt.where(BillingLedger.ledger_month == ledger_month)
    if case_id:
        stmt = stmt.where(BillingLedger.case_id == case_id)
    if billable_status:
        stmt = stmt.where(BillingLedger.billable_status == BillableStatus(billable_status.upper()))
    rows = db.scalars(stmt.limit(500)).all()
    return [_serialize_ledger(r, include_finance=True) for r in rows]


def override_billable(
    db: Session,
    ledger_id: int,
    *,
    billable_status: str,
    override_reason: str,
    user_id: int,
) -> dict:
    row = db.get(BillingLedger, ledger_id)
    if not row:
        raise ValueError("Ledger row not found")
    if row.billable_status == BillableStatus.INVOICED:
        raise ValueError("Cannot override invoiced ledger row")
    row.billable_status = BillableStatus(billable_status.upper())
    row.override_reason = override_reason.strip()
    row.overridden_by_user_id = user_id
    db.flush()
    return _serialize_ledger(row, include_finance=True)


def _serialize_ledger(row: BillingLedger, *, include_finance: bool) -> dict:
    case = row.case
    data = {
        "id": row.id,
        "caseId": row.case_id,
        "caseCode": case.case_code if case else "",
        "ledgerMonth": row.ledger_month,
        "eventDate": row.event_date.isoformat(),
        "eventType": row.event_type.value,
        "sourceType": row.source_type.value,
        "sourceId": row.source_id,
        "sessionId": row.session_id,
        "dailyLogId": row.daily_log_id,
        "billableStatus": row.billable_status.value,
        "quantity": float(row.quantity),
        "rateInr": float(row.rate_inr),
        "amountInr": float(row.amount_inr),
        "gstRatePercent": float(row.gst_rate_percent) if row.gst_rate_percent is not None else None,
        "gstAmountInr": float(row.gst_amount_inr) if row.gst_amount_inr is not None else None,
        "hsnSacCode": row.hsn_sac_code,
        "totalInr": float(row.total_inr),
        "clientInvoiceId": row.client_invoice_id,
        "adminNote": row.admin_note,
        "overrideReason": row.override_reason,
        "productBillingRuleId": row.product_billing_rule_id,
    }
    if include_finance:
        data["payoutAmountInr"] = float(row.payout_amount_inr) if row.payout_amount_inr is not None else None
        data["insighteMarginInr"] = float(row.insighte_margin_inr) if row.insighte_margin_inr is not None else None
    return data


def reconcile_month(db: Session, *, case_id: int, billing_month: str) -> dict:
    from sqlalchemy import extract, func

    from app.models.invoice_line import InvoiceSessionLine

    ledger_rows = db.scalars(
        select(BillingLedger).where(
            BillingLedger.case_id == case_id,
            BillingLedger.ledger_month == billing_month,
        )
    ).all()
    client_billable = sum(
        float(r.total_inr)
        for r in ledger_rows
        if r.billable_status in (BillableStatus.BILLABLE, BillableStatus.INVOICED)
    )
    session_ids = [r.session_id for r in ledger_rows if r.session_id]
    therapist_payout = 0.0
    if session_ids:
        lines = db.scalars(
            select(InvoiceSessionLine).where(InvoiceSessionLine.session_id.in_(session_ids))
        ).all()
        therapist_payout = sum(float(l.payout_amount_inr or l.amount_inr or 0) for l in lines)

    year_s, month_s = billing_month.split("-")[:2]
    session_count = db.scalar(
        select(func.count(TherapySession.id)).where(
            TherapySession.case_id == case_id,
            extract("year", TherapySession.scheduled_date) == int(year_s),
            extract("month", TherapySession.scheduled_date) == int(month_s),
            TherapySession.status == SessionStatus.COMPLETED,
        )
    ) or 0
    return {
        "caseId": case_id,
        "billingMonth": billing_month,
        "sessionCount": session_count,
        "ledgerBillableTotalInr": client_billable,
        "therapistPayoutTotalInr": therapist_payout,
        "marginInr": round(client_billable - therapist_payout, 2),
        "ledgerRowCount": len(ledger_rows),
        "disputedRows": sum(1 for r in ledger_rows if r.dispute_status == LedgerDisputeStatus.OPEN),
    }


def consume_package_session(db: Session, *, case_id: int, session: TherapySession) -> BillingLedger | None:
    from app.models.client_billing import CarePackage, CarePackageStatus

    pkg = db.scalars(
        select(CarePackage)
        .where(
            CarePackage.case_id == case_id,
            CarePackage.status == CarePackageStatus.ACTIVE,
        )
        .order_by(CarePackage.id.desc())
    ).first()
    if not pkg or pkg.used_sessions >= pkg.total_sessions:
        return None
    pkg.used_sessions += 1
    if pkg.used_sessions >= pkg.total_sessions:
        pkg.status = CarePackageStatus.EXHAUSTED
    case = db.get(Case, case_id)
    rule = _resolve_rule(db, case) if case else None
    row = BillingLedger(
        case_id=case_id,
        parent_user_id=pkg.parent_user_id,
        therapist_user_id=session.therapist_user_id,
        product_billing_rule_id=pkg.product_billing_rule_id or (rule.id if rule else None),
        source_type=LedgerSourceType.PACKAGE_CONSUMPTION,
        source_id=session.id,
        session_id=session.id,
        care_package_id=pkg.id,
        ledger_month=_ledger_month(session.scheduled_date),
        event_date=session.scheduled_date,
        event_type=LedgerEventType.PACKAGE_CONSUMPTION,
        billable_status=BillableStatus.BILLABLE,
        quantity=1,
        rate_inr=0,
        amount_inr=0,
        total_inr=0,
    )
    db.add(row)
    db.flush()
    return row
