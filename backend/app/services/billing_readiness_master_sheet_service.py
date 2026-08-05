"""Billing Readiness Master Sheet — read-only compose from InsighteCase sources only."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.billing_readiness_exception_rule import (
    BillingReadinessExceptionRule,
    BillingReadinessExceptionSeverity,
    BillingReadinessExceptionType,
)
from app.models.case import BillingType, Case, CaseStatus, ClientBillingMode
from app.models.child import Child
from app.models.client_billing import ClientInvoice, ClientInvoiceLine, ClientInvoiceLineType, ClientInvoiceStatus
from app.models.ledger_billing import BillableStatus, BillingLedger, LedgerDisputeStatus, LedgerEventType
from app.models.report import MonthlyReport, ReportStatus
from app.models.user import User
from app.services import billing_composer_service, case_finance_note_service

NOT_CONFIGURED = "Not yet configured"
NOT_AVAILABLE = "Not yet available"

_EXCEPTION_ORDER = (
    BillingReadinessExceptionType.INVOICE_ENGINE_AMOUNT_MISMATCH,
    BillingReadinessExceptionType.STATUS_CONFLICT,
    BillingReadinessExceptionType.SESSION_COUNT_MISMATCH,
    BillingReadinessExceptionType.LEAVE_MISMATCH,
    BillingReadinessExceptionType.MISSING_INVOICE_NUMBER,
    BillingReadinessExceptionType.REPORTS_NOT_SUBMITTED,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _client_type_label(case: Case) -> str:
    if case.billing_type == BillingType.PACKAGE:
        return "Package"
    module = (case.product_module or "").lower()
    if module == "shadow_support":
        return "Shadow"
    if module == "homecare":
        return "Homecare"
    if case.billing_type == BillingType.MONTHLY_FIXED:
        return "Monthly fixed"
    return case.product_module or NOT_CONFIGURED


def _prepaid_postpaid(case: Case) -> str:
    if case.client_billing_mode == ClientBillingMode.PREPAID:
        return "Prepaid"
    if case.client_billing_mode == ClientBillingMode.POSTPAID:
        return "Postpaid"
    return NOT_CONFIGURED


def _active_therapist(db: Session, case_id: int) -> tuple[int | None, str]:
    row = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.desc())
        .limit(1)
    ).first()
    if not row:
        return None, "—"
    user = db.get(User, row.therapist_user_id)
    name = user.full_name if user and user.full_name else f"Therapist {row.therapist_user_id}"
    return row.therapist_user_id, name


def _zoho_id(db: Session, client_invoice_id: int | None) -> str:
    if not client_invoice_id:
        return NOT_AVAILABLE
    try:
        from sqlalchemy import inspect

        from app.services import external_ref_service

        if not inspect(db.get_bind()).has_table("external_refs"):
            return NOT_AVAILABLE
        ext = external_ref_service.get_external_id_db(
            db, provider="ZOHO_BOOKS", entity_type="client_invoice", entity_id=client_invoice_id
        )
        return ext or NOT_AVAILABLE
    except Exception:
        return NOT_AVAILABLE


def _activity_counts(db: Session, *, case_id: int, billing_month: str, case: Case | None = None) -> dict[str, Any]:
    rows = db.scalars(
        select(BillingLedger).where(
            BillingLedger.case_id == case_id,
            BillingLedger.ledger_month == billing_month,
        )
    ).all()
    sessions_delivered = sum(
        1
        for r in rows
        if r.event_type
        in (LedgerEventType.SESSION_COMPLETED, LedgerEventType.PACKAGE_CONSUMPTION)
        and r.billable_status in (BillableStatus.BILLABLE, BillableStatus.INVOICED, BillableStatus.PENDING_REVIEW)
    )
    package_consumed = sum(
        1 for r in rows if r.event_type == LedgerEventType.PACKAGE_CONSUMPTION
    )
    if package_consumed == 0 and case and case.billing_type == BillingType.PACKAGE:
        from app.models.client_billing import CarePackage
        from app.models.client_package_cycle import ClientPackageCycle

        cycle = db.scalars(
            select(ClientPackageCycle)
            .where(ClientPackageCycle.case_id == case_id)
            .order_by(ClientPackageCycle.id.desc())
            .limit(1)
        ).first()
        if cycle and cycle.consumed_sessions:
            package_consumed = int(cycle.consumed_sessions)
        else:
            pkg = db.scalars(
                select(CarePackage).where(CarePackage.case_id == case_id).limit(1)
            ).first()
            if pkg and pkg.used_sessions:
                package_consumed = int(pkg.used_sessions)
    if package_consumed > sessions_delivered:
        sessions_delivered = package_consumed
    leaves = sum(1 for r in rows if r.event_type == LedgerEventType.LEAVE_DEDUCTION)
    child_absence = sum(1 for r in rows if r.event_type == LedgerEventType.CHILD_ABSENT)
    extra_sessions = sum(1 for r in rows if r.event_type == LedgerEventType.MANUAL_ADJUSTMENT)
    disputed_sessions = sum(1 for r in rows if r.dispute_status == LedgerDisputeStatus.OPEN)
    return {
        "sessionsDelivered": sessions_delivered,
        "packageSessionsConsumed": package_consumed,
        "leaves": leaves,
        "childAbsence": child_absence,
        "extraSessions": extra_sessions,
        "disputedSessions": disputed_sessions,
        "source": "billing_ledger",
    }


def _raised_invoice_metrics(db: Session, inv: ClientInvoice | None) -> dict[str, Any]:
    if not inv:
        return {
            "invoiceId": None,
            "invoiceNumber": None,
            "sessionCount": None,
            "leaveCount": None,
            "amountInr": None,
        }
    lines = db.scalars(select(ClientInvoiceLine).where(ClientInvoiceLine.client_invoice_id == inv.id)).all()
    session_count = sum(
        1
        for ln in lines
        if (ln.line_item_type or "").upper() in ("SESSION_CHARGE", ClientInvoiceLineType.SESSION_CHARGE.value)
    )
    leave_count = sum(
        1
        for ln in lines
        if (ln.line_item_type or "").upper() in ("LEAVE_ADJUSTMENT", ClientInvoiceLineType.LEAVE_ADJUSTMENT.value)
    )
    snap = inv.billing_snapshot if isinstance(inv.billing_snapshot, dict) else {}
    if session_count == 0 and snap.get("sessionsBillable") is not None:
        session_count = int(snap.get("sessionsBillable") or 0)
    if leave_count == 0 and snap.get("leavesTotal") is not None:
        leave_count = int(snap.get("leavesTotal") or 0)
    return {
        "invoiceId": inv.id,
        "invoiceNumber": inv.invoice_number,
        "sessionCount": session_count,
        "leaveCount": leave_count,
        "amountInr": round(float(inv.total_inr or 0), 2),
    }


def _load_exception_rules(db: Session) -> dict[BillingReadinessExceptionType, BillingReadinessExceptionRule]:
    try:
        rows = db.scalars(select(BillingReadinessExceptionRule).where(BillingReadinessExceptionRule.active.is_(True))).all()
    except Exception:
        return {}
    return {r.exception_type: r for r in rows}


def _default_rules() -> dict[BillingReadinessExceptionType, dict[str, Any]]:
    """Fallback when migration table is empty (e.g. SQLite test DB before seed)."""
    return {
        BillingReadinessExceptionType.SESSION_COUNT_MISMATCH: {"tolerance": 0.0, "severity": "WARN"},
        BillingReadinessExceptionType.LEAVE_MISMATCH: {"tolerance": 0.0, "severity": "WARN"},
        BillingReadinessExceptionType.INVOICE_ENGINE_AMOUNT_MISMATCH: {"tolerance": 1.0, "severity": "BLOCK"},
        BillingReadinessExceptionType.MISSING_INVOICE_NUMBER: {"tolerance": 0.0, "severity": "WARN"},
        BillingReadinessExceptionType.REPORTS_NOT_SUBMITTED: {"tolerance": 0.0, "severity": "WARN"},
        BillingReadinessExceptionType.STATUS_CONFLICT: {"tolerance": 0.0, "severity": "BLOCK"},
    }


def _rule_for(
    rules: dict[BillingReadinessExceptionType, BillingReadinessExceptionRule],
    exc_type: BillingReadinessExceptionType,
) -> dict[str, Any]:
    row = rules.get(exc_type)
    if row:
        return {"tolerance": float(row.tolerance or 0), "severity": row.severity.value}
    return _default_rules().get(exc_type, {"tolerance": 0.0, "severity": "WARN"})


def _monthly_report_ok(db: Session, *, case_id: int, billing_month: str) -> bool:
    rep = db.scalars(
        select(MonthlyReport)
        .where(MonthlyReport.case_id == case_id, MonthlyReport.month == billing_month)
        .limit(1)
    ).first()
    if not rep:
        return False
    return rep.status in (ReportStatus.APPROVED, ReportStatus.PUBLISHED)


def _status_is_inactive(status: CaseStatus) -> bool:
    return status in (CaseStatus.DEACTIVATED, CaseStatus.CLOSED, CaseStatus.SUSPENDED)


def _evaluate_exceptions(
    *,
    case: Case,
    billing_month: str,
    activity: dict[str, Any],
    raised: dict[str, Any],
    engine_amount: float | None,
    preview: dict[str, Any],
    rules: dict[BillingReadinessExceptionType, BillingReadinessExceptionRule],
    db: Session,
) -> tuple[list[dict[str, Any]], str, bool]:
    hits: list[dict[str, Any]] = []
    activity_sessions = int(activity.get("sessionsDelivered") or 0)
    activity_leaves = int(activity.get("leaves") or 0)
    overview = preview.get("overview") or {}

    if raised.get("sessionCount") is not None:
        session_diff = int(raised["sessionCount"]) - activity_sessions
    else:
        session_diff = int(overview.get("sessionsCompleted") or 0) - int(overview.get("sessionsBillable") or 0)

    if raised.get("leaveCount") is not None:
        leave_diff = int(raised["leaveCount"]) - activity_leaves
    else:
        leave_diff = int(overview.get("leavesTotal") or 0) - activity_leaves

    amount_diff = None
    if raised.get("amountInr") is not None and engine_amount is not None:
        amount_diff = round(float(raised["amountInr"]) - float(engine_amount), 2)

    def _add(exc_type: BillingReadinessExceptionType, delta: float, message: str) -> None:
        cfg = _rule_for(rules, exc_type)
        tol = float(cfg["tolerance"])
        if abs(delta) <= tol:
            return
        hits.append(
            {
                "type": exc_type.value,
                "severity": cfg["severity"],
                "delta": delta,
                "message": message,
                "tolerance": tol,
            }
        )

    _add(
        BillingReadinessExceptionType.SESSION_COUNT_MISMATCH,
        float(session_diff),
        f"Session count diff {session_diff:+d} (raised vs activity)",
    )
    _add(
        BillingReadinessExceptionType.LEAVE_MISMATCH,
        float(leave_diff),
        f"Leave diff {leave_diff:+d} (raised vs activity)",
    )
    if amount_diff is not None:
        _add(
            BillingReadinessExceptionType.INVOICE_ENGINE_AMOUNT_MISMATCH,
            amount_diff,
            f"Invoice vs engine amount diff ₹{amount_diff:+.2f}",
        )

    has_activity = activity_sessions > 0 or activity_leaves > 0
    if has_activity and not raised.get("invoiceNumber"):
        _add(
            BillingReadinessExceptionType.MISSING_INVOICE_NUMBER,
            1.0,
            "Billable activity present without a client invoice for this month",
        )

    if has_activity and not _monthly_report_ok(db, case_id=case.id, billing_month=billing_month):
        _add(
            BillingReadinessExceptionType.REPORTS_NOT_SUBMITTED,
            1.0,
            "Monthly report not approved or published for this billing month",
        )

    if _status_is_inactive(case.status) and has_activity:
        _add(
            BillingReadinessExceptionType.STATUS_CONFLICT,
            1.0,
            f"Case status {case.status.value} with billable activity in {billing_month}",
        )

    severity_rank = {"BLOCK": 2, "WARN": 1, "CLEAR": 0}
    money_state = "CLEAR"
    held = False
    for hit in hits:
        if hit["type"] == BillingReadinessExceptionType.REPORTS_NOT_SUBMITTED.value:
            continue
        sev = hit["severity"]
        if severity_rank.get(sev, 0) > severity_rank.get(money_state, 0):
            money_state = sev
        if sev == BillingReadinessExceptionSeverity.BLOCK.value:
            held = True

    state = money_state
    if money_state == "CLEAR" and any(
        h["type"] == BillingReadinessExceptionType.REPORTS_NOT_SUBMITTED.value for h in hits
    ):
        state = "CLEAR"

    hits.sort(
        key=lambda h: next(
            (i for i, e in enumerate(_EXCEPTION_ORDER) if e.value == h["type"]),
            99,
        )
    )
    return hits, state, held


def _insighte_share(case: Case, engine_preview: dict) -> str | float:
    margin = engine_preview.get("overview", {}).get("estimatedMargin")
    if margin is not None:
        return round(float(margin), 2)
    if case.compensation_mode and case.client_rate_per_session_inr and case.pay_share_amount_inr:
        return NOT_CONFIGURED
    return NOT_CONFIGURED


def _client_billing_rate(case: Case) -> str | float:
    if case.billing_type == BillingType.MONTHLY_FIXED and case.client_monthly_rate_inr is not None:
        return round(float(case.client_monthly_rate_inr), 2)
    if case.billing_type == BillingType.PACKAGE and case.package_amount_inr is not None:
        return round(float(case.package_amount_inr), 2)
    if case.client_rate_per_session_inr is not None:
        return round(float(case.client_rate_per_session_inr), 2)
    return NOT_CONFIGURED


def compose_master_sheet_row(db: Session, *, case: Case, billing_month: str) -> dict[str, Any]:
    ym = billing_composer_service.normalize_billing_month(billing_month)
    therapist_id, therapist_name = _active_therapist(db, case.id)
    cm_name = "—"
    if case.case_manager_user_id:
        cm = db.get(User, case.case_manager_user_id)
        cm_name = cm.full_name if cm and cm.full_name else f"User {case.case_manager_user_id}"

    inv = db.scalars(
        select(ClientInvoice)
        .where(ClientInvoice.case_id == case.id, ClientInvoice.billing_month == ym)
        .order_by(ClientInvoice.id.desc())
        .limit(1)
    ).first()

    preview = billing_composer_service.get_composer_preview(db, case_id=case.id, billing_month=ym)
    engine_amount = preview.get("overview", {}).get("total")
    engine_amount = round(float(engine_amount), 2) if engine_amount is not None else None

    activity = _activity_counts(db, case_id=case.id, billing_month=ym, case=case)
    raised = _raised_invoice_metrics(db, inv)
    rules = _load_exception_rules(db)
    exceptions, exception_state, held = _evaluate_exceptions(
        case=case,
        billing_month=ym,
        activity=activity,
        raised=raised,
        engine_amount=engine_amount,
        preview=preview,
        rules=rules,
        db=db,
    )

    session_diff = None
    leave_diff = None
    amount_diff = None
    if raised.get("sessionCount") is not None:
        session_diff = int(raised["sessionCount"]) - int(activity["sessionsDelivered"])
    else:
        session_diff = int(preview.get("overview", {}).get("sessionsCompleted") or 0) - int(
            preview.get("overview", {}).get("sessionsBillable") or 0
        )
    if raised.get("leaveCount") is not None:
        leave_diff = int(raised["leaveCount"]) - int(activity["leaves"])
    else:
        leave_diff = int(preview.get("overview", {}).get("leavesTotal") or 0) - int(activity["leaves"])
    if raised.get("amountInr") is not None and engine_amount is not None:
        amount_diff = round(float(raised["amountInr"]) - float(engine_amount), 2)

    start_date = None
    first_assign = db.scalar(
        select(func.min(CaseAssignment.start_date)).where(CaseAssignment.case_id == case.id)
    )
    if first_assign:
        start_date = first_assign.isoformat()

    notes_by_scope = case_finance_note_service.latest_notes_by_scope(
        db, case_id=case.id, billing_month=ym
    )

    return {
        "caseId": case.id,
        "caseCode": case.case_code,
        "zohoId": _zoho_id(db, inv.id if inv else None),
        "clientName": case.child.full_name if case.child else "—",
        "childName": case.child.full_name if case.child else "—",
        "therapistId": therapist_id,
        "therapistName": therapist_name,
        "serviceType": case.service_type,
        "clientType": _client_type_label(case),
        "clientStatus": case.status.value if case.status else NOT_CONFIGURED,
        "caseManagerName": cm_name,
        "startDate": start_date or NOT_AVAILABLE,
        "prepaidPostpaid": _prepaid_postpaid(case),
        "billingInputs": {
            "clientBillingRate": _client_billing_rate(case),
            "insighteShare": _insighte_share(case, preview),
        },
        "activity": activity,
        "engineAmountInr": engine_amount,
        "engineSource": "billing_composer_service.get_composer_preview",
        "reconciliation": {
            "raisedInvoiceNumber": raised.get("invoiceNumber"),
            "raisedInvoiceSessions": raised.get("sessionCount"),
            "raisedInvoiceLeaves": raised.get("leaveCount"),
            "raisedInvoiceAmountInr": raised.get("amountInr"),
            "sessionCountDiff": session_diff,
            "leaveDiff": leave_diff,
            "amountDiffInr": amount_diff,
            "activitySource": "billing_ledger_and_sessions",
            "raisedInvoiceSource": "client_invoices",
        },
        "comments": {
            "crm": notes_by_scope.get("crm") or NOT_AVAILABLE,
            "hr": notes_by_scope.get("hr") or NOT_AVAILABLE,
            "notes": notes_by_scope.get("finance") or case.notes or NOT_AVAILABLE,
        },
        "exceptionState": exception_state,
        "exceptions": exceptions,
        "held": held,
        "clientInvoiceStatus": inv.status.value if inv and inv.status else "NONE",
        "viewHref": f"/admin/cases/{case.id}",
        "composerHref": f"/admin/invoices/compose?case_id={case.id}&billing_month={ym}",
    }


def list_billing_readiness_master_sheet(
    db: Session,
    *,
    billing_month: str | None = None,
    service_type: str | None = None,
    client_type: str | None = None,
    client_status: str | None = None,
    exception_state: str | None = None,
    search: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    ym = billing_composer_service.normalize_billing_month(
        billing_month or datetime.now(timezone.utc).strftime("%Y-%m")
    )
    limit = max(1, min(int(limit or 200), 500))

    stmt = (
        select(Case)
        .where(Case.billing_type.is_not(None))
        .options(selectinload(Case.child))
        .order_by(Case.id)
    )
    if client_status:
        try:
            stmt = stmt.where(Case.status == CaseStatus(client_status.upper()))
        except ValueError:
            pass
    elif not client_status:
        stmt = stmt.where(Case.status == CaseStatus.ACTIVE)

    if service_type:
        stmt = stmt.where(Case.service_type.ilike(f"%{service_type.strip()}%"))

    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.join(Child, Case.child_id == Child.id).where(
            or_(
                Case.case_code.ilike(q),
                Child.full_name.ilike(q),
                Case.service_type.ilike(q),
            )
        )

    cases = list(db.scalars(stmt.limit(limit * 3)).all())
    items: list[dict[str, Any]] = []
    for case in cases:
        row = compose_master_sheet_row(db, case=case, billing_month=ym)
        if client_type:
            ct = (client_type or "").strip().lower()
            if ct and ct not in (row.get("clientType") or "").lower():
                continue
        if exception_state:
            want = exception_state.strip().upper()
            if want != (row.get("exceptionState") or "").upper():
                continue
        items.append(row)
        if len(items) >= limit:
            break

    return {
        "billingMonth": ym,
        "asOf": _now_iso(),
        "count": len(items),
        "items": items,
        "readOnly": True,
        "sources": ["client_invoices", "billing_ledger", "therapy_sessions", "billing_composer_service"],
    }
