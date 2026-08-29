"""Hard-delete a case and dependent rows by case_code (maintenance only)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

DELETE_CASE_SQL = """
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


def case_snapshot(db: Session, case_code: str) -> dict | None:
    row = db.execute(
        text(
            """
            SELECT c.id, c.case_code, c.status, c.child_id,
                   ch.first_name || ' ' || ch.last_name AS child_name
            FROM cases c
            JOIN children ch ON ch.id = c.child_id
            WHERE c.case_code = :case_code
            """
        ),
        {"case_code": case_code},
    ).mappings().first()
    return dict(row) if row else None


def delete_case_by_code(db: Session, case_code: str) -> dict:
    """Hard-delete one case by case_code. Caller must commit."""
    before = case_snapshot(db, case_code)
    if not before:
        raise ValueError(f"Case not found: {case_code}")

    for stmt in DELETE_CASE_SQL.strip().split(";"):
        sql = stmt.strip()
        if sql:
            db.execute(text(sql), {"case_code": case_code})

    after = case_snapshot(db, case_code)
    if after is not None:
        raise RuntimeError(f"Case still exists after delete: {case_code}")

    return {
        "deleted": True,
        "case_code": case_code,
        "case_id": before["id"],
        "child_id": before["child_id"],
        "child_name": before["child_name"],
    }
