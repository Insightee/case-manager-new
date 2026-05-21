"""
Comprehensive review regression tests (plan: comprehensive_app_review).
Covers auth, workbench, pipeline, reschedule, billing, tickets, robustness.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.slot import SlotStatus, TherapistSlot
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import api_items

client = TestClient(app)

REVIEW_ROLES = [
    ("superadmin@demo.com", "admin"),
    ("therapist@demo.com", "therapist"),
    ("parent@demo.com", "parent"),
    ("casemanager@demo.com", "admin"),
    ("finance@demo.com", "admin"),
    ("viewer@demo.com", "admin"),
    ("hr@demo.com", "hr"),
]


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_login(email)}"}


@pytest.mark.parametrize("email,expected_portal_hint", REVIEW_ROLES)
def test_role_auth_me_returns_permissions(email: str, expected_portal_hint: str):
    h = _headers(email)
    me = client.get("/api/v1/auth/me", headers=h)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body.get("email") == email
    assert body.get("roles")
    assert body.get("permissions") is not None


def test_workbench_all_expected_sections_superadmin():
    wb = client.get("/api/v1/admin/workbench/summary", headers=_headers("superadmin@demo.com"))
    assert wb.status_code == 200, wb.text
    sections = wb.json().get("sections", {})
    for key in ("reports", "logs", "reschedules", "tickets", "incidents", "iep", "meetings"):
        assert key in sections, f"missing workbench section {key}"


def test_workbench_cm_has_scoped_sections():
    wb = client.get("/api/v1/admin/workbench/summary", headers=_headers("casemanager@demo.com"))
    assert wb.status_code == 200
    assert "sections" in wb.json()


def test_pipeline_board_has_action_columns():
    board = client.get("/api/v1/admin/cases/pipeline", headers=_headers("superadmin@demo.com"))
    assert board.status_code == 200, board.text
    col_ids = {c["id"] for c in board.json()["columns"]}
    for expected in (
        "pending_allotment",
        "needs_therapist",
        "reassignment",
        "reports_logs",
        "iep",
        "active",
    ):
        assert expected in col_ids


def test_reschedule_confirm_clears_pending_and_workbench():
    therapist_h = _headers("therapist@demo.com")
    parent_h = _headers("parent@demo.com")
    admin_h = _headers("superadmin@demo.com")

    start = date(2026, 11, 3)
    end = start + timedelta(days=6)
    client.post(
        "/api/v1/scheduling/template/materialize",
        headers=therapist_h,
        params={"from_date": start.isoformat(), "to_date": end.isoformat()},
    )

    cases_r = client.get("/api/v1/parent/cases", headers=parent_h)
    cases = cases_r.json()
    if not cases:
        pytest.skip("No parent cases")
    case_id = cases[0]["id"]
    therapists = client.get(f"/api/v1/booking/therapists?case_id={case_id}", headers=parent_h).json()
    tid = therapists[0]["therapist_user_id"]

    cal = client.get(
        f"/api/v1/parent/booking/calendar?case_id={case_id}&therapist_id={tid}"
        f"&from_date={start.isoformat()}&to_date={end.isoformat()}",
        headers=parent_h,
    )
    available = [s for s in cal.json()["slots"] if s.get("display_status") == "available"]
    if len(available) < 2:
        pytest.skip("Need two bookable slots")
    old_id, new_id = available[0]["id"], available[1]["id"]

    book = client.post(
        "/api/v1/booking/appointments",
        headers=parent_h,
        json={"case_id": case_id, "slot_id": old_id},
    )
    assert book.status_code in (200, 201), book.text

    resched = client.post(
        f"/api/v1/parent/appointments/{old_id}/reschedule",
        headers=parent_h,
        json={"new_slot_id": new_id},
    )
    assert resched.status_code == 200, resched.text

    wb_before = client.get("/api/v1/admin/workbench/summary", headers=admin_h)
    assert wb_before.status_code == 200
    pending_items = wb_before.json().get("sections", {}).get("reschedules", {}).get("items", [])
    assert any(i.get("id") == new_id for i in pending_items)

    confirm = client.post(
        f"/api/v1/scheduling/slots/{new_id}/confirm-reschedule",
        headers=therapist_h,
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json().get("approval_status") == "CONFIRMED"

    wb_after = client.get("/api/v1/admin/workbench/summary", headers=admin_h)
    pending_after = wb_after.json().get("sections", {}).get("reschedules", {}).get("items", [])
    assert not any(i.get("id") == new_id for i in pending_after)


def test_invoice_submit_finance_approve_and_breakdown():
    therapist_h = _headers("therapist@demo.com")
    finance_h = _headers("finance@demo.com")

    preview = client.get("/api/v1/invoices/preview?month=2026-05", headers=therapist_h)
    assert preview.status_code == 200, preview.text
    if preview.json().get("total_sessions", 0) == 0:
        pytest.skip("No billable sessions for May 2026")

    submit = client.post(
        "/api/v1/invoices/submit",
        headers=therapist_h,
        json={"month": "2026-05", "notes": "Review test submit"},
    )
    if submit.status_code == 400 and "already submitted" in submit.json().get("detail", "").lower():
        listed = client.get("/api/v1/invoices", headers=therapist_h)
        invoices = listed.json() if isinstance(listed.json(), list) else listed.json().get("items", [])
        may_inv = next((i for i in invoices if "2026" in str(i.get("month", ""))), None)
        if not may_inv:
            pytest.skip("May invoice exists but not listable")
        invoice_id = may_inv["id"]
    else:
        assert submit.status_code == 201, submit.text
        invoice_id = submit.json()["id"]

    breakdown = client.get(f"/api/v1/invoices/{invoice_id}/breakdown", headers=finance_h)
    assert breakdown.status_code == 200, breakdown.text
    assert breakdown.json().get("cases") is not None or breakdown.json().get("lines") is not None

    approve = client.post(
        f"/api/v1/invoices/{invoice_id}/approve",
        headers=finance_h,
        json={"comment": "Approved in comprehensive review test"},
    )
    assert approve.status_code == 200, approve.text


def test_parent_ticket_create_and_staff_reply():
    parent_h = _headers("parent@demo.com")
    admin_h = _headers("superadmin@demo.com")

    cases = client.get("/api/v1/parent/cases", headers=parent_h).json()
    case_id = cases[0]["id"] if cases else None

    created = client.post(
        "/api/v1/parent/support-requests",
        headers=parent_h,
        json={
            "subject": "Review test ticket",
            "message": "Parent needs help with scheduling",
            "topic": "SCHEDULING",
            "case_id": case_id,
        },
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]

    reply = client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=admin_h,
        json={"body": "Staff reply from review test", "is_internal": False},
    )
    assert reply.status_code == 201, reply.text

    detail = client.get(f"/api/v1/tickets/{ticket_id}", headers=admin_h)
    assert detail.status_code == 200
    messages = detail.json().get("messages") or []
    assert any("Staff reply" in (m.get("body") or "") for m in messages)


def test_staff_ticket_escalate():
    th = _headers("therapist@demo.com")
    admin_h = _headers("superadmin@demo.com")

    created = client.post(
        "/api/v1/tickets",
        headers=th,
        json={"subject": "Escalate test", "body": "Need manager", "category": "OTHER"},
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]
    level_before = created.json().get("escalation_level") or 0

    esc = client.post(f"/api/v1/tickets/{ticket_id}/escalate", headers=admin_h)
    assert esc.status_code == 200, esc.text
    assert esc.json().get("escalation_level", 0) >= level_before


def test_viewer_cannot_create_assignment():
    viewer_h = _headers("viewer@demo.com")
    cases = client.get("/api/v1/cases", headers=viewer_h)
    assert cases.status_code == 200
    case_id = api_items(cases.json())[0]["id"]

    assign = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=viewer_h,
        json={
            "therapist_user_id": 1,
            "start_date": date.today().isoformat(),
            "reason_for_change": "Should fail",
        },
    )
    assert assign.status_code == 403


def test_confirm_reschedule_invalid_slot_returns_400():
    therapist_h = _headers("therapist@demo.com")
    slots = client.get(
        f"/api/v1/slots?from_date={date.today().isoformat()}&to_date={(date.today() + timedelta(days=7)).isoformat()}",
        headers=therapist_h,
    )
    rows = slots.json() if isinstance(slots.json(), list) else slots.json().get("items", [])
    confirmed = next((s for s in rows if s.get("approval_status") == "CONFIRMED"), None)
    if not confirmed:
        pytest.skip("No confirmed slot to test negative path")
    bad = client.post(
        f"/api/v1/scheduling/slots/{confirmed['id']}/confirm-reschedule",
        headers=therapist_h,
    )
    assert bad.status_code == 400


def test_case_not_found_returns_404():
    admin_h = _headers("superadmin@demo.com")
    r = client.get("/api/v1/cases/999999", headers=admin_h)
    assert r.status_code == 404


def test_hr_therapists_list():
    hr_h = _headers("hr@demo.com")
    listed = client.get("/api/v1/hr/therapists", headers=hr_h)
    assert listed.status_code == 200, listed.text
    assert len(api_items(listed.json())) >= 1


def test_unified_calendar_with_case_filter():
    therapist_h = _headers("therapist@demo.com")
    cases = client.get("/api/v1/cases", headers=therapist_h)
    items = cases.json() if isinstance(cases.json(), list) else cases.json().get("items", [])
    if not items:
        pytest.skip("No cases")
    case_id = items[0]["id"]
    start = date.today()
    end = start + timedelta(days=6)
    cal = client.get(
        f"/api/v1/scheduling/calendar?from_date={start.isoformat()}&to_date={end.isoformat()}"
        f"&case_id={case_id}",
        headers=therapist_h,
    )
    assert cal.status_code == 200
    assert "slots" in cal.json()
