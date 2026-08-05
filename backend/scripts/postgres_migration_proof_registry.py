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
    from app.models.case import Case
    from app.models.finance_writable import (
        CaseFinanceNote,
        CaseFinanceNoteScope,
        CaseFinanceNoteType,
        FinanceCorrectionProposal,
        FinanceCorrectionProposalType,
        FinanceProposalStatus,
        FinanceWrongSide,
    )

    case = db.scalar(select(Case).limit(1))
    if not case:
        raise RuntimeError("Need seeded cases — run demo_seed first")

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
    return {"proposal_id": proposal.id, "note_id": note.id}


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
