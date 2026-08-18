"""Revision-scoped seed + assertion metadata for Postgres migration proof.

Each Alembic head revision that adds schema must register:
- seed(): insert at least one FK-backed row per new table/column group
- tables_added / columns_added: checked after downgrade(parent)
"""
from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

SeedFn = Callable[[Session], dict[str, Any]]

_REGISTRY: dict[str, dict[str, Any]] = {}


def register_head(
    revision: str,
    *,
    tables_added: list[str],
    columns_added: list[tuple[str, str]] | None = None,
    seed: SeedFn | None = None,
) -> None:
    _REGISTRY[revision] = {
        "tables_added": tables_added,
        "columns_added": columns_added or [],
        "seed": seed,
    }


def head_config(revision: str) -> dict[str, Any] | None:
    return _REGISTRY.get(revision)


def all_registered_revisions() -> list[str]:
    return list(_REGISTRY.keys())


def _seed_n8o9p0q1r2s3(db: Session) -> dict[str, Any]:
    from app.models.client_billing import CarePackage, ClientInvoice, ClientPayment, PaymentMethod
    from app.models.client_package_cycle import ClientPackageCycle
    from app.models.external_ref import ExternalRef

    inv = db.scalar(select(ClientInvoice).limit(1))
    if not inv:
        raise RuntimeError("No client_invoices row — run demo_seed first")

    pkg = db.scalar(select(CarePackage).where(CarePackage.case_id == inv.case_id).limit(1))
    if not pkg:
        pkg = CarePackage(
            case_id=inv.case_id,
            parent_user_id=inv.parent_user_id,
            name="Migration proof package",
            total_sessions=10,
            used_sessions=0,
        )
        db.add(pkg)
        db.flush()

    cycle = ClientPackageCycle(
        care_package_id=pkg.id,
        case_id=inv.case_id,
        cycle_index=99,
        billed_sessions=10,
        consumed_sessions=0,
        remaining_sessions=10,
        client_invoice_id=inv.id,
    )
    db.add(cycle)

    ext = ExternalRef(
        provider="ZOHO_BOOKS",
        entity_type="client_invoice",
        entity_id=inv.id,
        external_id="MIGRATION-PROOF-ZOHO-001",
    )
    db.add(ext)

    pay = ClientPayment(
        client_invoice_id=inv.id,
        amount_inr=100.0,
        method=PaymentMethod.UPI,
        reference="MIGRATION-PROOF-GW",
        gateway_provider="MOCK",
        gateway_payment_id="gw_migration_proof_001",
        provider_ref="mock_ref_001",
    )
    db.add(pay)
    db.flush()
    return {"cycle_id": cycle.id, "external_ref_id": ext.id, "payment_id": pay.id}


def _seed_c9d0e1f2a3b5(db: Session) -> dict[str, Any]:
    from app.models.billing_period_snapshot import (
        BillingMonthClose,
        BillingMonthCloseStatus,
        CaseBillingPeriodSnapshot,
    )
    from app.models.case import Case
    from app.models.client_billing import ClientInvoice

    inv = db.scalar(select(ClientInvoice).limit(1))
    case = db.scalar(select(Case).limit(1))
    if not inv or not case:
        raise RuntimeError("Need seeded client_invoices and cases — run demo_seed first")

    if inv.billing_snapshot is None:
        inv.billing_snapshot = {"proof": True, "source": "migration_proof_seed"}

    close = db.scalar(
        select(BillingMonthClose).where(BillingMonthClose.billing_month == "2099-12")
    )
    if not close:
        close = BillingMonthClose(
            billing_month="2099-12",
            status=BillingMonthCloseStatus.CLOSED,
            payout_preview_rows=[{"caseId": case.id, "proof": True}],
            notes="Postgres migration proof seed",
        )
        db.add(close)
        db.flush()

    snap = db.scalar(
        select(CaseBillingPeriodSnapshot).where(
            CaseBillingPeriodSnapshot.case_id == case.id,
            CaseBillingPeriodSnapshot.billing_month == "2099-12",
        )
    )
    if not snap:
        snap = CaseBillingPeriodSnapshot(
            case_id=case.id,
            billing_month="2099-12",
            billing_snapshot={"proof": True},
            client_invoice_id=inv.id,
            ledger_subtotal_inr=100.0,
            ledger_tax_inr=0.0,
            ledger_total_inr=100.0,
            session_count=1,
        )
        db.add(snap)
        db.flush()

    return {"billing_month_close_id": close.id, "case_billing_period_snapshot_id": snap.id}


def _seed_d0e1f2a3b4c6(db: Session) -> dict[str, Any]:
    from app.models.billing_readiness_exception_rule import (
        BillingReadinessExceptionRule,
        BillingReadinessExceptionSeverity,
        BillingReadinessExceptionType,
    )

    inserted = 0
    for exc_type in BillingReadinessExceptionType:
        exists = db.scalar(
            select(BillingReadinessExceptionRule.id).where(
                BillingReadinessExceptionRule.exception_type == exc_type
            )
        )
        if exists:
            continue
        sev = (
            BillingReadinessExceptionSeverity.BLOCK
            if exc_type
            in (
                BillingReadinessExceptionType.INVOICE_ENGINE_AMOUNT_MISMATCH,
                BillingReadinessExceptionType.STATUS_CONFLICT,
            )
            else BillingReadinessExceptionSeverity.WARN
        )
        tol = 1.0 if exc_type == BillingReadinessExceptionType.INVOICE_ENGINE_AMOUNT_MISMATCH else 0.0
        db.add(
            BillingReadinessExceptionRule(
                exception_type=exc_type,
                tolerance=tol,
                severity=sev,
                active=True,
                description=f"Migration proof seed for {exc_type.value}",
            )
        )
        inserted += 1
    db.flush()
    return {"rules_inserted": inserted}


register_head(
    "n8o9p0q1r2s3",
    tables_added=["client_package_cycles", "external_refs"],
    columns_added=[
        ("client_payments", "gateway_provider"),
        ("client_payments", "gateway_payment_id"),
        ("client_payments", "provider_ref"),
    ],
    seed=_seed_n8o9p0q1r2s3,
)

register_head(
    "c9d0e1f2a3b5",
    tables_added=["billing_month_closes", "case_billing_period_snapshots"],
    columns_added=[("client_invoices", "billing_snapshot")],
    seed=_seed_c9d0e1f2a3b5,
)

register_head(
    "d0e1f2a3b4c6",
    tables_added=["billing_readiness_exception_rules"],
    columns_added=[],
    seed=_seed_d0e1f2a3b4c6,
)


def _seed_e1f2a3b4c5d7(db: Session) -> dict[str, Any]:
    from app.models.assignment import CaseAssignment
    from app.models.case import Case
    from app.models.finance_writable import (
        CaseFinanceNote,
        CaseFinanceNoteScope,
        CaseFinanceNoteType,
        FinanceCorrectionProposal,
        FinanceCorrectionProposalType,
        FinancePayoutDeduction,
        FinancePayoutDeductionDirection,
        FinancePayoutDeductionStatus,
        FinanceProposalStatus,
        FinanceWrongSide,
    )
    from sqlalchemy import text

    case = db.scalar(select(Case).limit(1))
    if not case:
        raise RuntimeError("Need seeded cases — run demo_seed first")

    assignment = db.scalar(select(CaseAssignment).where(CaseAssignment.case_id == case.id).limit(1))
    therapist_user_id = assignment.therapist_user_id if assignment else 1

    proposal = FinanceCorrectionProposal(
        case_id=case.id,
        billing_month="2099-11",
        proposal_type=FinanceCorrectionProposalType.CORRECT_RESHARE,
        wrong_side=FinanceWrongSide.INVOICE_WRONG,
        status=FinanceProposalStatus.REJECTED,
        reason="Migration proof seed — rejected placeholder",
        old_client_amount_inr=100.0,
        new_client_amount_inr=100.0,
        created_by_user_id=1,
    )
    db.add(proposal)
    db.flush()

    deduction = FinancePayoutDeduction(
        case_id=case.id,
        billing_month="2099-11",
        therapist_user_id=therapist_user_id,
        amount_inr=50.0,
        direction=FinancePayoutDeductionDirection.DEDUCT,
        note_type=CaseFinanceNoteType.OTHER,
        reason="Migration proof seed — payout deduction placeholder",
        status=FinancePayoutDeductionStatus.ACTIVE,
        created_by_user_id=1,
    )
    db.add(deduction)
    db.flush()

    note = CaseFinanceNote(
        case_id=case.id,
        billing_month="2099-11",
        note_scope=CaseFinanceNoteScope.CRM,
        note_type=CaseFinanceNoteType.OTHER,
        reason="Migration proof CRM note seed",
        author_user_id=1,
    )
    db.add(note)
    db.flush()

    # Greenfield create_all stamps per-column indexes; e1f2 downgrade drops composite names.
    db.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_finance_correction_proposals_case_month "
            "ON finance_correction_proposals (case_id, billing_month)"
        )
    )
    db.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_finance_payout_deductions_case_month "
            "ON finance_payout_deductions (case_id, billing_month)"
        )
    )
    db.flush()
    return {"proposal_id": proposal.id, "deduction_id": deduction.id, "note_id": note.id}


register_head(
    "e1f2a3b4c5d7",
    tables_added=[
        "finance_correction_proposals",
        "finance_payout_deductions",
        "case_finance_notes",
    ],
    columns_added=[],
    seed=_seed_e1f2a3b4c5d7,
)


def _seed_f2a3b4c5d6e8(db: Session) -> dict[str, Any]:
    from app.models.invoice import Invoice, InvoiceStatus
    from app.models.therapist_payout_settlement import TherapistPayoutBatch, TherapistPayoutTransfer

    existing = db.scalar(
        select(TherapistPayoutBatch).where(TherapistPayoutBatch.idempotency_key == "MIGRATION-PROOF-PAYOUT-001")
    )
    if existing:
        return {"batch_id": existing.id, "skipped": True}

    inv = db.scalar(
        select(Invoice)
        .where(Invoice.status == InvoiceStatus.APPROVED)
        .where(~Invoice.id.in_(select(TherapistPayoutTransfer.invoice_id)))
        .limit(1)
    )
    if not inv:
        inv = db.scalar(select(Invoice).limit(1))
    if not inv:
        raise RuntimeError("Need seeded invoices — run demo_seed first")

    batch = TherapistPayoutBatch(
        billing_month="2099-12",
        status="EXPORTED",
        provider="MOCK",
        idempotency_key="MIGRATION-PROOF-PAYOUT-001",
        provider_batch_ref="MOCK-BATCH-MIGRATION",
        created_by_user_id=1,
    )
    db.add(batch)
    db.flush()
    xfer = TherapistPayoutTransfer(
        batch_id=batch.id,
        invoice_id=inv.id,
        gross_inr=100.0,
        tds_rate_percent=10.0,
        tds_inr=10.0,
        deductions_inr=0,
        net_inr=90.0,
        provider_ref="MOCK-XFER-MIGRATION",
        status="PENDING",
    )
    db.add(xfer)
    db.flush()
    return {"batch_id": batch.id, "transfer_id": xfer.id}


register_head(
    "f2a3b4c5d6e8",
    tables_added=["therapist_payout_batches", "therapist_payout_transfers"],
    columns_added=[
        ("therapist_profiles", "tds_rate_percent"),
        ("invoices", "tds_inr"),
        ("invoices", "net_payable_inr"),
    ],
    seed=_seed_f2a3b4c5d6e8,
)


def _seed_g2b3c4d5e6f9(db: Session) -> dict[str, Any]:
    from datetime import date

    from app.models.case import Case
    from app.models.client_billing import (
        BillingDispute,
        BillingDisputeStatus,
        ClientInvoice,
        ClientInvoiceStatus,
        ClientInvoiceType,
    )
    from app.models.support_ticket import SupportTicket, TicketCategory, TicketStatus, TicketTopic

    dispute = db.scalar(
        select(BillingDispute).where(BillingDispute.reason_code == "MIGRATION-PROOF-DISPUTE")
    )
    if not dispute:
        inv = db.scalar(
            select(ClientInvoice).where(ClientInvoice.invoice_number == "MIGRATION-PROOF-DISPUTE-INV")
        )
        if not inv:
            inv = db.scalar(select(ClientInvoice).limit(1))
        if not inv:
            case = db.scalar(select(Case).limit(1))
            if not case:
                raise RuntimeError("Need seeded cases — run demo_seed first")
            inv = ClientInvoice(
                invoice_number="MIGRATION-PROOF-DISPUTE-INV",
                parent_user_id=1,
                case_id=case.id,
                invoice_type=ClientInvoiceType.POSTPAID,
                status=ClientInvoiceStatus.GENERATED,
                billing_month="2099-10",
                service_type=case.service_type or "Migration proof",
                product_module=case.product_module or "homecare",
                due_date=date(2099, 10, 15),
                subtotal_inr=100.0,
                tax_inr=0,
                discount_inr=0,
                package_deduction_inr=0,
                adjustment_inr=0,
                total_inr=100.0,
                amount_paid_inr=0,
                notes="Migration proof seed — minimal client invoice for dispute linkage",
            )
            db.add(inv)
            db.flush()

        dispute = BillingDispute(
            client_invoice_id=inv.id,
            parent_user_id=inv.parent_user_id,
            reason_code="MIGRATION-PROOF-DISPUTE",
            message="Migration proof seed — billing dispute placeholder",
            status=BillingDisputeStatus.OPEN,
        )
        db.add(dispute)
        db.flush()

    existing_ticket = db.scalar(
        select(SupportTicket).where(SupportTicket.billing_dispute_id == dispute.id).limit(1)
    )
    if existing_ticket:
        if dispute.support_ticket_id != existing_ticket.id:
            dispute.support_ticket_id = existing_ticket.id
            db.flush()
        return {"ticket_id": existing_ticket.id, "dispute_id": dispute.id, "skipped": True}

    ticket = SupportTicket(
        case_id=inv.case_id if (inv := db.get(ClientInvoice, dispute.client_invoice_id)) else 1,
        raised_by_user_id=dispute.parent_user_id,
        category=TicketCategory.FINANCE,
        topic=TicketTopic.BILLING_PAYMENT,
        subject="Migration proof billing dispute",
        body="Migration proof seed",
        status=TicketStatus.OPEN,
        billing_dispute_id=dispute.id,
        client_invoice_id=dispute.client_invoice_id,
    )
    db.add(ticket)
    db.flush()
    dispute.support_ticket_id = ticket.id
    db.flush()
    return {"ticket_id": ticket.id, "dispute_id": dispute.id}


register_head(
    "g2b3c4d5e6f9",
    tables_added=[],
    columns_added=[
        ("billing_disputes", "support_ticket_id"),
        ("support_tickets", "billing_dispute_id"),
        ("support_tickets", "client_invoice_id"),
        ("finance_correction_proposals", "billing_dispute_id"),
    ],
    seed=_seed_g2b3c4d5e6f9,
)


def _seed_f3a4b5c6d7e9(db: Session) -> dict[str, Any]:
    from app.models.support_ticket import SupportTicket

    ticket = db.scalar(select(SupportTicket).limit(1))
    if not ticket:
        raise RuntimeError("Need seeded support tickets — run demo_seed first")
    if not ticket.escalated_to_department:
        ticket.escalated_to_department = "OPERATIONS"
        db.flush()
    return {"ticket_id": ticket.id, "escalated_to_department": ticket.escalated_to_department}


register_head(
    "f3a4b5c6d7e9",
    tables_added=[],
    columns_added=[("support_tickets", "escalated_to_department")],
    seed=_seed_f3a4b5c6d7e9,
)


def _seed_h4i5j6k7l8m9(db: Session) -> dict[str, Any]:
    """Merge-only head — schema ownership stays on parent revisions."""
    return {"merge_only": True}


register_head(
    "h4i5j6k7l8m9",
    tables_added=[],
    columns_added=[],
    seed=_seed_h4i5j6k7l8m9,
)


def _seed_ba5p6p7r8v9(db: Session) -> dict[str, Any]:
    from app.models.billing_approval_request import BillingApprovalRequest, BillingApprovalStatus
    from app.models.case import Case
    from app.models.user import User

    existing = db.scalar(
        select(BillingApprovalRequest.id).where(
            BillingApprovalRequest.projected_profit_inr == 4999.00
        )
    )
    if existing:
        return {"request_id": existing, "skipped": True}

    case = db.scalar(select(Case).limit(1))
    requester = db.scalar(select(User).where(User.email == "casemanager@demo.com"))
    if not case or not requester:
        raise RuntimeError("Need seeded cases and case manager — run demo_seed first")

    row = BillingApprovalRequest(
        case_id=case.id,
        status=BillingApprovalStatus.PENDING,
        previous_billing={"proof": "migration_proof", "client_rate_per_session_inr": 5000},
        proposed_billing={"proof": "migration_proof", "client_rate_per_session_inr": 4500},
        projected_profit_inr=4999.00,
        requested_by_user_id=requester.id,
    )
    db.add(row)
    db.flush()
    return {"request_id": row.id}


register_head(
    "ba5p6p7r8v9",
    tables_added=["billing_approval_requests"],
    columns_added=[],
    seed=_seed_ba5p6p7r8v9,
)


def _seed_s4e5v6i7d8e9(db: Session) -> dict[str, Any]:
    from app.models.case import Case
    from app.models.daily_log import DailyLog
    from app.models.iep_identity import IepGoalItem, IepStrategyItem
    from app.models.iep_plan import IepPlan
    from app.models.session_evidence import SessionGoalEntry, StrategyUseEvent
    from app.models.user import User

    existing = db.scalar(
        select(SessionGoalEntry.id).where(SessionGoalEntry.participation == "engaged").limit(1)
    )
    if existing:
        return {"goal_entry_id": existing, "skipped": True}

    log = db.scalar(select(DailyLog).limit(1))
    case = db.scalar(select(Case).limit(1))
    author = db.scalar(select(User).limit(1))
    if not log or not case or not author:
        raise RuntimeError("Need seeded daily_logs, cases, and users — run demo_seed first")

    plan = db.scalar(select(IepPlan).where(IepPlan.case_id == case.id).limit(1))
    if not plan:
        plan = IepPlan(
            case_id=case.id,
            version="migration-proof-v1",
            status="DRAFT",
            sections_json='{"schema_version":2,"learning_environments":[]}',
            created_by_user_id=author.id,
        )
        db.add(plan)
        db.flush()

    goal = IepGoalItem(
        iep_plan_id=plan.id,
        statement="Migration proof goal — request help with words",
    )
    strategy = IepStrategyItem(
        iep_plan_id=plan.id,
        statement="Migration proof strategy — visual schedule",
    )
    db.add(goal)
    db.add(strategy)
    db.flush()

    goal_entry = SessionGoalEntry(
        daily_log_id=log.id,
        goal_id=goal.id,
        participation="engaged",
        support_level="independent",
        achievement="progressing",
        created_by_user_id=author.id,
    )
    strat_event = StrategyUseEvent(
        daily_log_id=log.id,
        strategy_id=strategy.id,
        response="helpful",
    )
    db.add(goal_entry)
    db.add(strat_event)
    db.flush()
    return {
        "goal_item_id": goal.id,
        "strategy_item_id": strategy.id,
        "goal_entry_id": goal_entry.id,
        "strategy_event_id": strat_event.id,
    }


register_head(
    "s4e5v6i7d8e9",
    tables_added=[
        "iep_goal_items",
        "iep_strategy_items",
        "session_goal_entries",
        "strategy_use_events",
    ],
    columns_added=[],
    seed=_seed_s4e5v6i7d8e9,
)


def assert_head_absent(engine, revision: str) -> None:
    cfg = head_config(revision)
    if not cfg:
        return
    insp = inspect(engine)
    for table in cfg["tables_added"]:
        if insp.has_table(table):
            raise AssertionError(f"After downgrade, table {table!r} should be dropped (rev {revision})")
    for table, column in cfg["columns_added"]:
        if insp.has_table(table):
            cols = {c["name"] for c in insp.get_columns(table)}
            if column in cols:
                raise AssertionError(
                    f"After downgrade, column {table}.{column} should be dropped (rev {revision})"
                )


def assert_head_present(engine, revision: str) -> None:
    cfg = head_config(revision)
    if not cfg:
        return
    insp = inspect(engine)
    for table in cfg["tables_added"]:
        if not insp.has_table(table):
            raise AssertionError(f"After upgrade, table {table!r} should exist (rev {revision})")
    for table, column in cfg["columns_added"]:
        if insp.has_table(table):
            cols = {c["name"] for c in insp.get_columns(table)}
            if column not in cols:
                raise AssertionError(
                    f"After upgrade, column {table}.{column} should exist (rev {revision})"
                )


def assert_core_tables_intact(engine) -> None:
    insp = inspect(engine)
    for table in ("users", "cases", "client_invoices"):
        if not insp.has_table(table):
            raise AssertionError(f"Core table {table!r} must remain after downgrade")
