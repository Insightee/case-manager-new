"""Seed one row each into n8o9p0q1r2s3 tables for Postgres migration proof.

Run after `alembic upgrade head` on a throwaway Postgres DB that already has
base client-billing rows (demo_seed or production snapshot).

Usage:
  export DATABASE_URL=postgresql+psycopg2://...
  python3 -m scripts.postgres_migration_proof_seed
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.client_billing import CarePackage, ClientInvoice, ClientPayment, PaymentMethod
from app.models.client_package_cycle import ClientPackageCycle
from app.models.external_ref import ExternalRef


def run() -> dict[str, int]:
    db = SessionLocal()
    try:
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
            cycle_index=1,
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
        db.commit()
        return {"cycle_id": cycle.id, "external_ref_id": ext.id, "payment_id": pay.id}
    finally:
        db.close()


if __name__ == "__main__":
    ids = run()
    print("Seeded migration proof rows:", ids)
