"""Reusable finance walkthrough fixture — ~10 IC-WK-* cases for money tests."""
from __future__ import annotations

import os
from datetime import date, datetime, time, timezone

BILLING_MONTH = "2026-08"
FIXTURE_CASE_CODES = tuple(f"IC-WK-{i:03d}" for i in range(1, 15))

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.core.permissions import RoleName
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CaseStatus, ClientBillingMode, CompensationMode
from app.models.child import Child
from app.models.client_billing import (
    BillingDispute,
    BillingDisputeStatus,
    CarePackage,
    CarePackageStatus,
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceLineType,
    ClientInvoiceStatus,
    ClientInvoiceType,
    ClientPayment,
    ClientPaymentStatus,
    PaymentMethod,
)
from app.models.client_package_cycle import ClientPackageCycle, PackageBillingMode
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine, InvoiceSessionLine, SessionLineSource, SessionLineType
from app.models.ledger_billing import BillableStatus, BillingLedger, LedgerEventType, LedgerSourceType
from app.models.finance_writable import (
    CaseFinanceNote,
    CaseFinanceNoteScope,
    CaseFinanceNoteType,
    FinancePayoutDeduction,
    FinancePayoutDeductionDirection,
    FinancePayoutDeductionStatus,
)
from app.models.parent import ParentGuardian
from app.models.therapist_statement_dispute import TherapistStatementDispute
from app.models.user import User
from app.seed.demo_seed import ensure_active_case_assignment, get_or_create_user, run as demo_seed_run


def _ledger_row(
    db,
    *,
    case_id: int,
    therapist_id: int,
    parent_id: int,
    event_type: LedgerEventType,
    event_date: date,
    amount: float,
    billable: BillableStatus = BillableStatus.BILLABLE,
    session_id: int | None = None,
) -> BillingLedger:
    row = BillingLedger(
        case_id=case_id,
        parent_user_id=parent_id,
        therapist_user_id=therapist_id,
        source_type=LedgerSourceType.SESSION if session_id else LedgerSourceType.MANUAL,
        source_id=session_id or case_id,
        session_id=session_id,
        ledger_month=BILLING_MONTH,
        event_date=event_date,
        event_type=event_type,
        billable_status=billable,
        quantity=1,
        rate_inr=amount,
        amount_inr=amount,
        total_inr=amount,
        payout_amount_inr=round(amount * 0.6, 2),
    )
    db.add(row)
    db.flush()
    return row


def _invoice(
    db,
    *,
    case: Case,
    parent_id: int,
    total: float,
    subtotal: float,
    status: ClientInvoiceStatus,
    invoice_number: str,
    due_date: date,
    lines: list[dict],
    amount_paid: float = 0,
) -> ClientInvoice:
    inv = ClientInvoice(
        invoice_number=invoice_number,
        parent_user_id=parent_id,
        case_id=case.id,
        invoice_type=ClientInvoiceType.POSTPAID,
        status=status,
        billing_month=BILLING_MONTH,
        service_type=case.service_type,
        product_module=case.product_module,
        due_date=due_date,
        subtotal_inr=subtotal,
        tax_inr=0,
        discount_inr=0,
        package_deduction_inr=0,
        adjustment_inr=0,
        total_inr=total,
        amount_paid_inr=amount_paid,
        billing_snapshot={"walkthroughSeed": True, "billingMonth": BILLING_MONTH},
    )
    db.add(inv)
    db.flush()
    for i, ln in enumerate(lines):
        db.add(
            ClientInvoiceLine(
                client_invoice_id=inv.id,
                session_date=ln.get("session_date", date(2026, 8, 5 + i)),
                therapist_name=ln.get("therapist_name", "Therapist Neha"),
                service_label=case.service_type,
                session_status=ln.get("session_status", "Completed"),
                amount_inr=ln["amount_inr"],
                line_item_type=ln.get("line_item_type", ClientInvoiceLineType.SESSION_CHARGE.value),
                sort_order=i + 1,
            )
        )
    db.flush()
    return inv


def _therapist_invoice(
    db,
    *,
    therapist_id: int,
    case: Case,
    share_inr: float,
    status: InvoiceStatus,
    month: str = BILLING_MONTH,
) -> Invoice:
    inv = Invoice(
        therapist_user_id=therapist_id,
        month=month,
        amount_inr=share_inr,
        subtotal_inr=share_inr,
        status=status,
        sessions_count=1,
    )
    db.add(inv)
    db.flush()
    cl = InvoiceCaseLine(
        invoice_id=inv.id,
        case_id=case.id,
        case_code=case.case_code or f"C-{case.id}",
        billing_type=case.billing_type.value if case.billing_type else "PER_SESSION",
        included_sessions=1,
        therapist_share_inr=share_inr,
    )
    db.add(cl)
    db.flush()
    db.add(
        InvoiceSessionLine(
            invoice_case_line_id=cl.id,
            session_date=date(2026, 8, 10),
            line_type=SessionLineType.PER_SESSION,
            amount_inr=share_inr,
            source=SessionLineSource.LOG,
            included=True,
        )
    )
    db.flush()
    return inv


def _cleanup_walkthrough_cases(db) -> None:
    """Remove prior IC-WK-* fixture rows so force re-seed is deterministic."""
    from app.models.client_billing import ClientInvoiceLine
    from app.models.finance_writable import CaseFinanceNote, FinanceCorrectionProposal, FinancePayoutDeduction

    case_ids = list(db.scalars(select(Case.id).where(Case.case_code.like("IC-WK-%"))).all())
    if not case_ids:
        return
    inv_ids = list(db.scalars(select(ClientInvoice.id).where(ClientInvoice.case_id.in_(case_ids))).all())
    if inv_ids:
        db.query(ClientInvoiceLine).filter(ClientInvoiceLine.client_invoice_id.in_(inv_ids)).delete(
            synchronize_session=False
        )
        db.query(ClientInvoice).filter(ClientInvoice.id.in_(inv_ids)).delete(synchronize_session=False)
    db.query(BillingLedger).filter(BillingLedger.case_id.in_(case_ids)).delete(synchronize_session=False)
    db.query(InvoiceCaseLine).filter(InvoiceCaseLine.case_id.in_(case_ids)).delete(synchronize_session=False)
    db.query(FinanceCorrectionProposal).filter(FinanceCorrectionProposal.case_id.in_(case_ids)).delete(
        synchronize_session=False
    )
    db.query(FinancePayoutDeduction).filter(FinancePayoutDeduction.case_id.in_(case_ids)).delete(
        synchronize_session=False
    )
    from app.models.therapist_payout_settlement import TherapistPayoutTransfer

    therapist_inv_ids = list(
        db.scalars(
            select(Invoice.id)
            .join(InvoiceCaseLine, InvoiceCaseLine.invoice_id == Invoice.id)
            .where(InvoiceCaseLine.case_id.in_(case_ids))
        ).all()
    )
    if therapist_inv_ids:
        xfer_ids = list(
            db.scalars(
                select(TherapistPayoutTransfer.id).where(TherapistPayoutTransfer.invoice_id.in_(therapist_inv_ids))
            ).all()
        )
        if xfer_ids:
            db.query(TherapistPayoutTransfer).filter(TherapistPayoutTransfer.id.in_(xfer_ids)).delete(
                synchronize_session=False
            )
        db.query(Invoice).filter(Invoice.id.in_(therapist_inv_ids)).delete(synchronize_session=False)
    db.query(CaseFinanceNote).filter(CaseFinanceNote.case_id.in_(case_ids)).delete(synchronize_session=False)
    db.query(Case).filter(Case.id.in_(case_ids)).delete(synchronize_session=False)
    db.commit()


def run(*, force: bool = False) -> dict:
    demo_seed_run()
    db = SessionLocal()
    report: dict = {"billingMonth": BILLING_MONTH, "cases": []}
    try:
        if force:
            _cleanup_walkthrough_cases(db)
        elif db.scalar(select(Case).where(Case.case_code == "IC-WK-001")):
            report["cases"] = [{"code": code, "condition": "existing"} for code in FIXTURE_CASE_CODES]
            report["note"] = "Fixture already present — skipped re-seed"
            return report

        parent = db.scalar(select(User).where(User.email == "parent@demo.com"))
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        case_mgr = db.scalar(select(User).where(User.email == "casemanager@demo.com"))
        finance = db.scalar(select(User).where(User.email == "finance@demo.com"))
        assert parent and therapist and case_mgr

        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == parent.id)).first()

        def add_child_case(
            code: str,
            first: str,
            last: str,
            *,
            product_module: str,
            service_type: str,
            billing_type: BillingType,
            rate: float | None = None,
            package_amount: float | None = None,
            package_sessions: int | None = None,
            pay_share: float | None = None,
            no_ratio: bool = False,
        ) -> Case:
            child = Child(first_name=first, last_name=last)
            db.add(child)
            db.flush()
            if pg and child not in pg.children:
                pg.children.append(child)
            case = db.scalars(select(Case).where(Case.case_code == code)).first()
            if not case:
                case = Case(
                    case_code=code,
                    child_id=child.id,
                    service_type=service_type,
                    product_module=product_module,
                    status=CaseStatus.ACTIVE,
                    case_manager_user_id=case_mgr.id,
                    client_billing_mode=ClientBillingMode.POSTPAID,
                )
                db.add(case)
            case.billing_type = billing_type
            case.client_rate_per_session_inr = rate
            case.package_amount_inr = package_amount
            case.package_session_count = package_sessions
            case.compensation_mode = CompensationMode.PERCENTAGE
            if no_ratio:
                case.pay_share_amount_inr = None
                case.therapist_fixed_pay_inr = None
            else:
                case.pay_share_amount_inr = pay_share or (rate * 0.6 if rate else 6000)
            db.flush()
            ensure_active_case_assignment(
                db,
                case_id=case.id,
                therapist_user_id=therapist.id,
                assigned_by_user_id=case_mgr.id,
                start_date=date(2026, 1, 1),
            )
            return case

        # --- Case definitions ---
        c_clean = add_child_case(
            "IC-WK-001", "Riya", "S.", product_module="shadow_support", service_type="Shadow Support",
            billing_type=BillingType.PER_SESSION, rate=1000, pay_share=600,
        )
        c_sess_mis = add_child_case(
            "IC-WK-002", "Dev", "P.", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=1200, pay_share=720,
        )
        c_leave_mis = add_child_case(
            "IC-WK-003", "Anya", "R.", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=1200, pay_share=720,
        )
        c_package = add_child_case(
            "IC-WK-004", "Kabir", "M.", product_module="homecare", service_type="Homecare Package",
            billing_type=BillingType.PACKAGE, package_amount=30000, package_sessions=10, pay_share=18000,
        )
        c_dispute = add_child_case(
            "IC-WK-005", "Meera", "K.", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=1200, pay_share=720,
        )
        c_no_ratio = add_child_case(
            "IC-WK-006", "NoRatio", "X.", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=1200, no_ratio=True,
        )
        c_overdue = add_child_case(
            "IC-WK-007", "Overdue", "O.", product_module="shadow_support", service_type="Shadow Support",
            billing_type=BillingType.PER_SESSION, rate=1000, pay_share=600,
        )
        c_paid = add_child_case(
            "IC-WK-008", "PaidUp", "P.", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=1200, pay_share=720,
        )
        c_claim = add_child_case(
            "IC-WK-009", "Claim", "C.", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=1200, pay_share=720,
        )
        c_payout = add_child_case(
            "IC-WK-010", "Priya", "T.", product_module="shadow_support", service_type="Shadow Support",
            billing_type=BillingType.PER_SESSION, rate=1000, pay_share=600,
        )
        c_payout_11 = add_child_case(
            "IC-WK-011", "Payout", "Eleven", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=10000, pay_share=10000,
        )
        c_payout_12 = add_child_case(
            "IC-WK-012", "Payout", "Twelve", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=3333, pay_share=3333,
        )
        c_payout_13 = add_child_case(
            "IC-WK-013", "Payout", "Thirteen", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=10000, pay_share=10000,
        )
        c_payout_14 = add_child_case(
            "IC-WK-014", "Payout", "Fourteen", product_module="homecare", service_type="Homecare",
            billing_type=BillingType.PER_SESSION, rate=1000, pay_share=1000,
        )

        # --- Ledger activity (2026-08) ---
        for i in range(4):
            _ledger_row(
                db, case_id=c_clean.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.SESSION_COMPLETED, event_date=date(2026, 8, 2 + i), amount=1000,
            )
        for i in range(4):
            _ledger_row(
                db, case_id=c_sess_mis.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.SESSION_COMPLETED, event_date=date(2026, 8, 3 + i), amount=1200,
            )
        for i in range(4):
            _ledger_row(
                db, case_id=c_leave_mis.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.SESSION_COMPLETED, event_date=date(2026, 8, 4 + i), amount=1200,
            )
        for i in range(4):
            _ledger_row(
                db, case_id=c_leave_mis.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.LEAVE_DEDUCTION, event_date=date(2026, 8, 20 + i), amount=0,
            )
        for i in range(8):
            _ledger_row(
                db, case_id=c_package.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.PACKAGE_CONSUMPTION, event_date=date(2026, 8, 1 + i), amount=3000,
            )
        for i in range(3):
            _ledger_row(
                db, case_id=c_dispute.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.SESSION_COMPLETED, event_date=date(2026, 8, 5 + i), amount=1200,
            )
        _ledger_row(
            db, case_id=c_no_ratio.id, therapist_id=therapist.id, parent_id=parent.id,
            event_type=LedgerEventType.SESSION_COMPLETED, event_date=date(2026, 8, 8), amount=1200,
        )
        for i in range(2):
            _ledger_row(
                db, case_id=c_overdue.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.SESSION_COMPLETED, event_date=date(2026, 8, 6 + i), amount=1000,
            )
        for i in range(3):
            _ledger_row(
                db, case_id=c_paid.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.SESSION_COMPLETED, event_date=date(2026, 8, 7 + i), amount=1200,
            )
        for i in range(2):
            _ledger_row(
                db, case_id=c_claim.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.SESSION_COMPLETED, event_date=date(2026, 8, 9 + i), amount=1200,
            )
        for i in range(3):
            _ledger_row(
                db, case_id=c_payout.id, therapist_id=therapist.id, parent_id=parent.id,
                event_type=LedgerEventType.SESSION_COMPLETED, event_date=date(2026, 8, 11 + i), amount=1000,
            )

        # --- Client invoices ---
        inv_clean = _invoice(
            db, case=c_clean, parent_id=parent.id, total=4000, subtotal=4000,
            status=ClientInvoiceStatus.SENT, invoice_number="INV-WK-001",
            due_date=date(2026, 8, 20),
            lines=[{"amount_inr": 1000} for _ in range(4)],
        )
        inv_sess = _invoice(
            db, case=c_sess_mis, parent_id=parent.id, total=6000, subtotal=6000,
            status=ClientInvoiceStatus.SENT, invoice_number="INV-WK-002",
            due_date=date(2026, 8, 25),
            lines=[{"amount_inr": 1200} for _ in range(5)],
        )
        inv_leave = _invoice(
            db, case=c_leave_mis, parent_id=parent.id, total=4800, subtotal=4800,
            status=ClientInvoiceStatus.SENT, invoice_number="INV-WK-003",
            due_date=date(2026, 8, 25),
            lines=[{"amount_inr": 1200, "line_item_type": ClientInvoiceLineType.SESSION_CHARGE.value} for _ in range(4)]
            + [{"amount_inr": 0, "line_item_type": ClientInvoiceLineType.LEAVE_ADJUSTMENT.value, "session_status": "Leave"} for _ in range(2)],
        )
        inv_pkg = _invoice(
            db, case=c_package, parent_id=parent.id, total=24000, subtotal=24000,
            status=ClientInvoiceStatus.SENT, invoice_number="INV-WK-004",
            due_date=date(2026, 8, 15),
            lines=[{"amount_inr": 3000, "line_item_type": ClientInvoiceLineType.PACKAGE_CHARGE.value} for _ in range(8)],
        )
        pkg = CarePackage(
            case_id=c_package.id,
            parent_user_id=parent.id,
            name="Walkthrough 10-pack",
            total_sessions=10,
            used_sessions=8,
            status=CarePackageStatus.ACTIVE,
        )
        db.add(pkg)
        db.flush()
        db.add(
            ClientPackageCycle(
                care_package_id=pkg.id,
                case_id=c_package.id,
                cycle_index=1,
                billed_sessions=10,
                consumed_sessions=8,
                remaining_sessions=2,
                billing_mode=PackageBillingMode.PACKAGE.value,
                client_invoice_id=inv_pkg.id,
            )
        )
        inv_dispute = _invoice(
            db, case=c_dispute, parent_id=parent.id, total=3600, subtotal=3600,
            status=ClientInvoiceStatus.SENT, invoice_number="INV-WK-005",
            due_date=date(2026, 8, 22),
            lines=[{"amount_inr": 1200} for _ in range(3)],
        )
        lines = db.scalars(select(ClientInvoiceLine).where(ClientInvoiceLine.client_invoice_id == inv_dispute.id)).all()
        db.add(
            BillingDispute(
                client_invoice_id=inv_dispute.id,
                client_invoice_line_id=lines[0].id,
                parent_user_id=parent.id,
                reason_code="incorrect_amount",
                message="Walkthrough: dispute on first session line",
                status=BillingDisputeStatus.OPEN,
            )
        )
        _invoice(
            db, case=c_no_ratio, parent_id=parent.id, total=1200, subtotal=1200,
            status=ClientInvoiceStatus.SENT, invoice_number="INV-WK-006",
            due_date=date(2026, 8, 20),
            lines=[{"amount_inr": 1200}],
        )
        inv_overdue = _invoice(
            db, case=c_overdue, parent_id=parent.id, total=2000, subtotal=2000,
            status=ClientInvoiceStatus.OVERDUE, invoice_number="INV-WK-007",
            due_date=date(2026, 7, 10),
            lines=[{"amount_inr": 1000} for _ in range(2)],
        )
        inv_paid = _invoice(
            db, case=c_paid, parent_id=parent.id, total=3600, subtotal=3600,
            status=ClientInvoiceStatus.PAID, invoice_number="INV-WK-008",
            due_date=date(2026, 8, 10), amount_paid=3600,
            lines=[{"amount_inr": 1200} for _ in range(3)],
        )
        inv_claim = _invoice(
            db, case=c_claim, parent_id=parent.id, total=2400, subtotal=2400,
            status=ClientInvoiceStatus.SENT, invoice_number="INV-WK-009",
            due_date=date(2026, 8, 28),
            lines=[{"amount_inr": 1200} for _ in range(2)],
        )
        db.add(
            ClientPayment(
                client_invoice_id=inv_claim.id,
                amount_inr=500,
                method=PaymentMethod.UPI,
                reference="WK-UPI-PENDING-001",
                payment_status=ClientPaymentStatus.PENDING_REVIEW,
                gateway_provider="MANUAL",
            )
        )
        _invoice(
            db, case=c_payout, parent_id=parent.id, total=3000, subtotal=3000,
            status=ClientInvoiceStatus.SENT, invoice_number="INV-WK-010",
            due_date=date(2026, 8, 25),
            lines=[{"amount_inr": 1000} for _ in range(3)],
        )

        # --- Therapist payout statements ---
        t_inv_sess = _therapist_invoice(
            db, therapist_id=therapist.id, case=c_sess_mis, share_inr=2880, status=InvoiceStatus.IN_REVIEW,
        )
        db.add(
            CaseFinanceNote(
                case_id=c_clean.id,
                billing_month=BILLING_MONTH,
                note_scope=CaseFinanceNoteScope.CRM,
                note_type=CaseFinanceNoteType.RETAINER,
                reason="Walkthrough fixture: family confirmed August billing",
                author_user_id=finance.id if finance else case_mgr.id,
            )
        )
        t_inv_ok = _therapist_invoice(db, therapist_id=therapist.id, case=c_payout, share_inr=1800, status=InvoiceStatus.IN_REVIEW)
        t_inv_11 = _therapist_invoice(
            db, therapist_id=therapist.id, case=c_payout_11, share_inr=10000, status=InvoiceStatus.APPROVED,
        )
        t_inv_12 = _therapist_invoice(
            db, therapist_id=therapist.id, case=c_payout_12, share_inr=3333, status=InvoiceStatus.APPROVED,
        )
        t_inv_13 = _therapist_invoice(
            db, therapist_id=therapist.id, case=c_payout_13, share_inr=10000, status=InvoiceStatus.APPROVED,
        )
        t_inv_14 = _therapist_invoice(
            db, therapist_id=therapist.id, case=c_payout_14, share_inr=1000, status=InvoiceStatus.APPROVED,
        )
        db.add(
            FinancePayoutDeduction(
                case_id=c_payout_13.id,
                billing_month=BILLING_MONTH,
                therapist_user_id=therapist.id,
                therapist_invoice_id=t_inv_13.id,
                amount_inr=500,
                direction=FinancePayoutDeductionDirection.DEDUCT,
                reason="Walkthrough fixture: post-TDS deduction",
                note_type=CaseFinanceNoteType.OTHER,
                created_by_user_id=finance.id if finance else case_mgr.id,
            )
        )
        db.add(
            FinancePayoutDeduction(
                case_id=c_payout_14.id,
                billing_month=BILLING_MONTH,
                therapist_user_id=therapist.id,
                therapist_invoice_id=t_inv_14.id,
                amount_inr=1100,
                direction=FinancePayoutDeductionDirection.DEDUCT,
                reason="Walkthrough fixture: over-deduct blocked",
                note_type=CaseFinanceNoteType.OTHER,
                created_by_user_id=finance.id if finance else case_mgr.id,
                status=FinancePayoutDeductionStatus.ACTIVE,
            )
        )
        t_inv_queried = _therapist_invoice(
            db, therapist_id=therapist.id, case=c_clean, share_inr=2400, status=InvoiceStatus.QUERIED,
        )
        db.add(
            TherapistStatementDispute(
                therapist_user_id=therapist.id,
                invoice_id=t_inv_queried.id,
                month=BILLING_MONTH,
                comment="Walkthrough: session count disagreement",
                disputed_session_ids=[90001],
                status="OPEN",
                prior_invoice_status=InvoiceStatus.IN_REVIEW.value,
            )
        )

        db.commit()

        report["cases"] = [
            {"code": "IC-WK-001", "condition": "CLEAN", "invoice": "INV-WK-001 ₹4000 / 4 sessions", "ledger": "4 sessions ₹4000", "pill": "CLEAR"},
            {"code": "IC-WK-002", "condition": "SESSION_MISMATCH", "invoice": "5 sessions ₹6000", "ledger": "4 sessions", "pill": "WARN session diff +1"},
            {"code": "IC-WK-003", "condition": "LEAVE_MISMATCH", "invoice": "2 leaves", "ledger": "4 leaves", "pill": "WARN leave diff -2"},
            {"code": "IC-WK-004", "condition": "PACKAGE_DRAWDOWN", "invoice": "8-pack drawdown ₹24000", "package": "8 consumed / 2 remaining", "pill": "CLEAR/WARN"},
            {"code": "IC-WK-005", "condition": "LINE_DISPUTE", "invoice": "INV-WK-005 ₹3600", "held": "line 1 ₹1200", "collectible": "₹2400"},
            {"code": "IC-WK-006", "condition": "NO_SHARE_RATIO", "invoice": "INV-WK-006", "correction": "BLOCKED"},
            {"code": "IC-WK-007", "condition": "OVERDUE", "invoice": "INV-WK-007 ₹2000 due 2026-07-10"},
            {"code": "IC-WK-008", "condition": "PAID", "invoice": "INV-WK-008 ₹3600 PAID"},
            {"code": "IC-WK-009", "condition": "PENDING_PAYMENT_CLAIM", "invoice": "INV-WK-009", "claim": "₹500 UPI pending"},
            {"code": "IC-WK-010", "condition": "PAYOUT_IN_REVIEW", "therapistInvoiceId": t_inv_ok.id},
            {"code": "IC-WK-011", "condition": "PAYOUT_APPROVED", "therapistInvoiceId": t_inv_11.id, "gross": 10000, "net": 9000},
            {"code": "IC-WK-012", "condition": "PAYOUT_NONROUND_TDS", "therapistInvoiceId": t_inv_12.id, "gross": 3333},
            {"code": "IC-WK-013", "condition": "PAYOUT_DEDUCTION", "therapistInvoiceId": t_inv_13.id, "deduction": 500},
            {"code": "IC-WK-014", "condition": "PAYOUT_BLOCKED", "therapistInvoiceId": t_inv_14.id},
            {"code": "(therapist)", "condition": "QUERIED_STATEMENT", "invoiceId": t_inv_queried.id, "status": "QUERIED"},
        ]
        report["logins"] = {
            "finance": "finance@demo.com / demo123",
            "parent": "parent@demo.com / demo123",
            "therapist": "therapist@demo.com / demo123",
        }
        return report
    finally:
        db.close()


if __name__ == "__main__":
    ensure_sqlite_schema_patches()
    out = run()
    import json
    print(json.dumps(out, indent=2))
