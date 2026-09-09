"""Package remaining single SOT (Core OS Stabilisation PR3 / DEC-01).

Canonical remaining lives on ``care_packages.used_sessions`` / ``total_sessions``.
``client_package_cycles`` is non-authoritative until a later epic — do not dual-write.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import BillingType, Case, ClientBillingMode
from app.models.client_billing import (
    CarePackage,
    CarePackageStatus,
    ClientInvoice,
    ClientInvoiceLine,
    ClientInvoiceStatus,
)
from app.models.session import Session as TherapySession

PACKAGE_CONSUMED_FLAG = "package_consumed"


class PackageEffectError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _session_has_times(session: TherapySession) -> bool:
    return bool(getattr(session, "actual_start_at", None) and getattr(session, "actual_end_at", None))


def _active_package(db: Session, case_id: int) -> CarePackage | None:
    return db.scalars(
        select(CarePackage)
        .where(
            CarePackage.case_id == case_id,
            CarePackage.status.in_([CarePackageStatus.ACTIVE, CarePackageStatus.EXHAUSTED]),
        )
        .order_by(CarePackage.id.desc())
    ).first()


def _consumption_ledger_row(db: Session, session_id: int):
    from app.models.ledger_billing import BillingLedger, LedgerSourceType

    return db.scalars(
        select(BillingLedger).where(
            BillingLedger.source_type == LedgerSourceType.PACKAGE_CONSUMPTION,
            BillingLedger.session_id == session_id,
        )
    ).first()


def session_package_invoice_locked(db: Session, session_id: int) -> bool:
    """True when session is on a generated/paid (non-draft/void) client invoice line."""
    row = db.scalars(
        select(ClientInvoiceLine.id)
        .join(ClientInvoice, ClientInvoice.id == ClientInvoiceLine.client_invoice_id)
        .where(
            ClientInvoiceLine.session_id == session_id,
            ClientInvoice.status.in_(
                [
                    ClientInvoiceStatus.GENERATED,
                    ClientInvoiceStatus.ISSUED,
                    ClientInvoiceStatus.SENT,
                    ClientInvoiceStatus.PARTIALLY_PAID,
                    ClientInvoiceStatus.PAID,
                    ClientInvoiceStatus.OVERDUE,
                    ClientInvoiceStatus.DISPUTED,
                    ClientInvoiceStatus.CLOSED,
                ]
            ),
        )
        .limit(1)
    ).first()
    return row is not None


def case_uses_package_sot(case: Case) -> bool:
    billing_type = case.billing_type.value if hasattr(case.billing_type, "value") else str(case.billing_type or "")
    mode = (
        case.client_billing_mode.value
        if hasattr(case.client_billing_mode, "value")
        else str(case.client_billing_mode or "")
    )
    return billing_type == BillingType.PACKAGE.value or mode == ClientBillingMode.PREPAID.value


def _session_package_consumed(session: TherapySession) -> bool:
    flag = getattr(session, "data_quality_flag", None)
    return flag == PACKAGE_CONSUMED_FLAG


def _mark_session_package_consumed(session: TherapySession) -> None:
    session.data_quality_flag = PACKAGE_CONSUMED_FLAG


def _clear_session_package_consumed(session: TherapySession) -> None:
    if getattr(session, "data_quality_flag", None) == PACKAGE_CONSUMED_FLAG:
        session.data_quality_flag = None


def apply_package_effect(
    db: Session,
    *,
    case_id: int,
    session: TherapySession,
    effect: str,
    require_times: bool = True,
) -> dict:
    """
    Apply package consume/reverse against care_packages SOT.

    effect: ``consume`` | ``reverse``
    ``used_sessions`` updates even when ``BILLING_LEDGER_WRITES`` is false.
    A PACKAGE_CONSUMPTION ledger row is used as the idempotency marker (always written on consume).
    """
    from app.models.ledger_billing import (
        BillableStatus,
        BillingLedger,
        LedgerEventType,
        LedgerSourceType,
    )
    from app.services.billing_ledger_service import _ledger_month, _ledger_writes_allowed, _resolve_rule

    if effect not in ("consume", "reverse"):
        raise PackageEffectError("INVALID_EFFECT", f"Unknown package effect: {effect}")

    existing = _consumption_ledger_row(db, session.id)
    if existing is None and _session_package_consumed(session):
        existing = True  # idempotency marker when ledger writes are disabled

    pkg = None
    if existing is not True and existing and existing.care_package_id:
        pkg = db.get(CarePackage, existing.care_package_id)
    if pkg is None:
        pkg = _active_package(db, case_id)

    if effect == "consume":
        if require_times and not _session_has_times(session):
            return {"applied": False, "reason": "NO_SESSION_TIMES"}
        if existing:
            ledger_id = existing.id if existing is not True else None
            return {
                "applied": False,
                "reason": "ALREADY_CONSUMED",
                "ledger_id": ledger_id,
                "package_id": pkg.id if pkg else None,
            }
        if not pkg or pkg.status == CarePackageStatus.PENDING_PAYMENT:
            return {"applied": False, "reason": "NO_ACTIVE_PACKAGE"}
        if pkg.used_sessions >= pkg.total_sessions:
            pkg.status = CarePackageStatus.EXHAUSTED
            db.flush()
            return {"applied": False, "reason": "PACKAGE_EXHAUSTED", "package_id": pkg.id}

        pkg.used_sessions += 1
        if pkg.used_sessions >= pkg.total_sessions:
            pkg.status = CarePackageStatus.EXHAUSTED
        else:
            pkg.status = CarePackageStatus.ACTIVE

        case = db.get(Case, case_id)
        rule = _resolve_rule(db, case) if case else None
        row = None
        if _ledger_writes_allowed():
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
        else:
            _mark_session_package_consumed(session)
            db.flush()
        return {
            "applied": True,
            "effect": "consume",
            "package_id": pkg.id,
            "used_sessions": pkg.used_sessions,
            "ledger_id": row.id if row else None,
        }

    # reverse
    if not existing and not _session_package_consumed(session):
        return {"applied": False, "reason": "NOT_CONSUMED"}
    if session_package_invoice_locked(db, session.id):
        raise PackageEffectError(
            "INVOICE_LOCKED",
            "This session is already on a client invoice — package reverse needs Finance review.",
        )
    if pkg is None:
        pkg = _active_package(db, case_id)
    if pkg and pkg.used_sessions > 0:
        pkg.used_sessions -= 1
        if pkg.status == CarePackageStatus.EXHAUSTED and pkg.used_sessions < pkg.total_sessions:
            pkg.status = CarePackageStatus.ACTIVE

    if existing is not True and existing:
        db.delete(existing)
    _clear_session_package_consumed(session)
    db.flush()
    return {
        "applied": True,
        "effect": "reverse",
        "package_id": pkg.id if pkg else None,
        "used_sessions": pkg.used_sessions if pkg else None,
    }


def maybe_consume_for_submitted_log(
    db: Session,
    *,
    case: Case | None,
    session: TherapySession | None,
) -> dict | None:
    """DEC-01: consume when timed log is submitted (PENDING) for package/prepaid cases."""
    if case is None or session is None or not case_uses_package_sot(case):
        return None
    return apply_package_effect(db, case_id=case.id, session=session, effect="consume", require_times=True)


def maybe_reverse_for_rejected_log(
    db: Session,
    *,
    case: Case | None,
    session: TherapySession | None,
) -> dict | None:
    if case is None or session is None or not case_uses_package_sot(case):
        return None
    return apply_package_effect(db, case_id=case.id, session=session, effect="reverse", require_times=False)
