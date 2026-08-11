"""Seed billing_readiness_exception_rules for Postgres migration proof."""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.billing_readiness_exception_rule import (
    BillingReadinessExceptionRule,
    BillingReadinessExceptionSeverity,
    BillingReadinessExceptionType,
)


def run() -> dict[str, int]:
    db = SessionLocal()
    try:
        before = db.scalar(select(BillingReadinessExceptionRule.id).limit(1))
        if before:
            count = db.scalar(select(func.count()).select_from(BillingReadinessExceptionRule)) or 0
            return {"rules": int(count), "inserted": 0}

        for exc_type in BillingReadinessExceptionType:
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
        db.commit()
        return {"rules": len(BillingReadinessExceptionType), "inserted": len(BillingReadinessExceptionType)}
    finally:
        db.close()


if __name__ == "__main__":
    print(run())
