#!/usr/bin/env python3
"""Delete a single case and its dependent rows by case_code (maintenance)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402

CASE_CODE = "IC-2026-SS-004"

DELETE_SQL = """
WITH target AS (
  SELECT id FROM cases WHERE case_code = :case_code
),
sess AS (
  SELECT id FROM sessions WHERE case_id IN (SELECT id FROM target)
),
case_invoices AS (
  SELECT id FROM client_invoices WHERE case_id IN (SELECT id FROM target)
),
iep AS (
  SELECT id FROM iep_plans WHERE case_id IN (SELECT id FROM target)
),
docs AS (
  SELECT id FROM case_documents WHERE case_id IN (SELECT id FROM target)
),
doc_versions AS (
  SELECT id FROM case_document_versions
  WHERE case_document_id IN (SELECT id FROM docs)
),
inc AS (
  SELECT id FROM incidents WHERE case_id IN (SELECT id FROM target)
),
tix AS (
  SELECT id FROM support_tickets WHERE case_id IN (SELECT id FROM target)
)
DELETE FROM billing_disputes
WHERE client_invoice_id IN (SELECT id FROM case_invoices);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
case_invoices AS (SELECT id FROM client_invoices WHERE case_id IN (SELECT id FROM target))
DELETE FROM client_payments WHERE client_invoice_id IN (SELECT id FROM case_invoices);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
sess AS (SELECT id FROM sessions WHERE case_id IN (SELECT id FROM target)),
case_invoices AS (SELECT id FROM client_invoices WHERE case_id IN (SELECT id FROM target))
DELETE FROM client_invoice_lines
WHERE client_invoice_id IN (SELECT id FROM case_invoices)
   OR session_id IN (SELECT id FROM sess);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM client_invoices WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM care_packages WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
sess AS (SELECT id FROM sessions WHERE case_id IN (SELECT id FROM target))
DELETE FROM invoice_session_lines WHERE session_id IN (SELECT id FROM sess);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM invoice_case_lines WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM invoice_manual_lines WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM billing_ledger WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM case_appointment_usage WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
sess AS (SELECT id FROM sessions WHERE case_id IN (SELECT id FROM target))
DELETE FROM daily_logs WHERE session_id IN (SELECT id FROM sess);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
sess AS (SELECT id FROM sessions WHERE case_id IN (SELECT id FROM target))
DELETE FROM appointment_reschedules
WHERE case_id IN (SELECT id FROM target)
   OR from_session_id IN (SELECT id FROM sess)
   OR to_session_id IN (SELECT id FROM sess);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
sess AS (SELECT id FROM sessions WHERE case_id IN (SELECT id FROM target))
UPDATE therapist_slots SET session_id = NULL WHERE session_id IN (SELECT id FROM sess);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM therapist_slots WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
sess AS (SELECT id FROM sessions WHERE case_id IN (SELECT id FROM target))
DELETE FROM sessions WHERE id IN (SELECT id FROM sess);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM report_images
WHERE report_type = 'monthly'
  AND report_id IN (SELECT id FROM monthly_reports WHERE case_id IN (SELECT id FROM target));

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM monthly_reports WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM observation_reports WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
iep AS (SELECT id FROM iep_plans WHERE case_id IN (SELECT id FROM target))
DELETE FROM iep_plan_suggestions WHERE iep_plan_id IN (SELECT id FROM iep);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM iep_plans WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
docs AS (SELECT id FROM case_documents WHERE case_id IN (SELECT id FROM target))
DELETE FROM case_document_workflow_events WHERE case_document_id IN (SELECT id FROM docs);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
docs AS (SELECT id FROM case_documents WHERE case_id IN (SELECT id FROM target))
DELETE FROM case_document_versions WHERE case_document_id IN (SELECT id FROM docs);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM case_documents WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM observation_checklists WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM case_clinical_profiles WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM document_comments WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
inc AS (SELECT id FROM incidents WHERE case_id IN (SELECT id FROM target))
DELETE FROM incident_attachments WHERE incident_id IN (SELECT id FROM inc);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
inc AS (SELECT id FROM incidents WHERE case_id IN (SELECT id FROM target))
DELETE FROM incident_messages WHERE incident_id IN (SELECT id FROM inc);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM incidents WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
tix AS (SELECT id FROM support_tickets WHERE case_id IN (SELECT id FROM target))
DELETE FROM ticket_attachments WHERE ticket_id IN (SELECT id FROM tix);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code),
tix AS (SELECT id FROM support_tickets WHERE case_id IN (SELECT id FROM target))
DELETE FROM ticket_messages WHERE ticket_id IN (SELECT id FROM tix);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM support_tickets WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM case_manager_meetings WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM case_status_requests WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM recurring_schedule_assignments WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM case_assignments WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM case_services WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM case_billing_preferences WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM attachments WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM parent_billing_statements WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
UPDATE therapist_leaves SET case_id = NULL WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
UPDATE audit_events SET case_id = NULL WHERE case_id IN (SELECT id FROM target);

WITH target AS (SELECT id FROM cases WHERE case_code = :case_code)
DELETE FROM notifications
WHERE entity_type = 'case' AND entity_id IN (SELECT id FROM target);

DELETE FROM cases WHERE case_code = :case_code;
"""


def _case_snapshot(db, case_code: str) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT c.id, c.case_code, c.status, c.child_id,
                   ch.first_name || ' ' || ch.last_name AS child_name
            FROM cases c
            JOIN children ch ON ch.id = c.child_id
            WHERE c.case_code = :case_code
               OR c.child_id IN (
                    SELECT child_id FROM cases WHERE case_code = :case_code
               )
            ORDER BY c.case_code
            """
        ),
        {"case_code": case_code},
    ).mappings().all()
    return [dict(r) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete one case by case_code")
    parser.add_argument("--case-code", default=CASE_CODE)
    parser.add_argument("--confirm", action="store_true", help="Required to execute delete")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        before_target = db.execute(
            text(
                """
                SELECT c.id, c.case_code, c.status, c.child_id,
                       ch.first_name || ' ' || ch.last_name AS child_name
                FROM cases c
                JOIN children ch ON ch.id = c.child_id
                WHERE c.case_code = :case_code
                """
            ),
            {"case_code": args.case_code},
        ).mappings().first()
        if not before_target:
            print(f"Case not found: {args.case_code}")
            return 1

        child_id = before_target["child_id"]
        sibling_cases = db.execute(
            text(
                """
                SELECT case_code, status FROM cases
                WHERE child_id = :child_id
                ORDER BY case_code
                """
            ),
            {"child_id": child_id},
        ).mappings().all()
        print("Before:")
        print(f"  Target: {dict(before_target)}")
        print(f"  All cases for child_id={child_id}:")
        for row in sibling_cases:
            print(f"    - {row['case_code']} ({row['status']})")

        if not args.confirm:
            print("Dry run only. Pass --confirm to delete.")
            return 0

        for stmt in DELETE_SQL.strip().split(";"):
            sql = stmt.strip()
            if sql:
                db.execute(text(sql), {"case_code": args.case_code})
        db.commit()

        remaining = db.execute(
            text(
                """
                SELECT case_code, status FROM cases
                WHERE child_id = :child_id
                ORDER BY case_code
                """
            ),
            {"child_id": child_id},
        ).mappings().all()
        gone = db.execute(
            text("SELECT 1 FROM cases WHERE case_code = :case_code"),
            {"case_code": args.case_code},
        ).first()
        print("After:")
        print(f"  {args.case_code} exists: {gone is not None}")
        print(f"  Remaining cases for child_id={child_id}:")
        for row in remaining:
            print(f"    - {row['case_code']} ({row['status']})")
        if gone is not None:
            print("ERROR: case still exists")
            return 1
        if len(remaining) != 1:
            print(f"WARNING: expected 1 remaining case, found {len(remaining)}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
