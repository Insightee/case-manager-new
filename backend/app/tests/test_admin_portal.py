from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import api_items

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_superadmin_dashboard_and_cases():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    dash = client.get("/api/v1/admin/dashboard/summary", headers=headers)
    assert dash.status_code == 200
    assert "open_cases" in dash.json()
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    assert len(api_items(cases.json())) >= 2


def test_case_manager_can_review_report():
    token = _login("casemanager@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    reports = client.get("/api/v1/reports/monthly", headers=headers)
    assert reports.status_code == 200
    under_review = [r for r in api_items(reports.json()) if r["status"] == "UNDER_REVIEW"]
    if under_review:
        rid = under_review[0]["id"]
        res = client.post(
            f"/api/v1/reports/monthly/{rid}/approve",
            headers=headers,
            json={"comment": "Approved in test", "visibility_status": "APPROVED_FOR_PARENT"},
        )
        assert res.status_code == 200


def test_parent_only_sees_parent_safe_reports():
    token = _login("parent@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    reports = client.get("/api/v1/parent/reports", headers=headers)
    assert reports.status_code == 200
    parent_safe = {"approved", "pending_review", "changes_requested", "acknowledged"}
    internal = {"UNDER_REVIEW", "DRAFT", "REJECTED"}
    for r in api_items(reports.json()):
        assert r["status"] in parent_safe
        assert r["status"] not in internal


def test_daily_log_requires_session():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    bad = client.post(
        "/api/v1/daily-logs",
        headers=headers,
        json={"session_id": 99999, "attendance_status": "PRESENT"},
    )
    assert bad.status_code in (400, 404)


def test_supervisor_dashboard():
    token = _login("supervisor@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    dash = client.get("/api/v1/admin/dashboard/summary", headers=headers)
    assert dash.status_code == 200


def test_finance_cannot_manage_users():
    token = _login("finance@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    users = client.get("/api/v1/admin/users", headers=headers)
    assert users.status_code == 403


def test_module_catalog_and_scoped_admin():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    catalog = client.get("/api/v1/admin/modules", headers=headers)
    assert catalog.status_code == 200
    assert "homecare" in catalog.json()["role_defaults"]["ADMIN"]

    scoped = _login("admin@demo.com")
    scoped_headers = {"Authorization": f"Bearer {scoped}"}
    me = client.get("/api/v1/auth/me", headers=scoped_headers)
    assert me.status_code == 200
    body = me.json()
    assert "homecare" in body["module_assignments"]
    assert "cases" in body["features"]
    assert "invoices" not in body["features"]

    cases = client.get("/api/v1/cases", headers=scoped_headers)
    assert cases.status_code == 200
    modules = {c["product_module"] for c in api_items(cases.json())}
    assert modules <= {"homecare"}


def test_create_user_requires_modules_for_admin():
    import uuid

    email = f"scoped-{uuid.uuid4().hex[:8]}@demo.com"
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    bad = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": "demo123",
            "full_name": "Scoped Only",
            "role_names": ["MODULE_ADMIN"],
            "module_assignments": [],
        },
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": "demo123",
            "full_name": "Scoped Only",
            "role_names": ["MODULE_ADMIN"],
            "module_assignments": ["shadow_support"],
        },
    )
    assert ok.status_code == 201
    assert ok.json()["module_assignments"] == ["shadow_support"]


def test_approve_log_makes_parent_visible():
    seed_run()
    admin_token = _login("casemanager@demo.com")
    parent_token = _login("parent@demo.com")
    headers = {"Authorization": f"Bearer {admin_token}"}
    logs = client.get("/api/v1/daily-logs?approval_status=PENDING", headers=headers)
    assert logs.status_code == 200
    pending = [l for l in logs.json() if l.get("parent_notes")]
    if not pending:
        return
    log_id = pending[0]["id"]
    res = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=headers)
    assert res.status_code == 200
    parent_headers = {"Authorization": f"Bearer {parent_token}"}
    parent_logs = client.get("/api/v1/parent/session-logs", headers=parent_headers)
    assert parent_logs.status_code == 200
    assert any(pl["id"] == log_id for pl in parent_logs.json())


def test_scoped_admin_dashboard_invoices_module():
    token = _login("admin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    dash = client.get("/api/v1/admin/dashboard/summary", headers=headers)
    assert dash.status_code == 200
    assert dash.json()["invoices_pending"] == 0


def test_incident_patch():
    token = _login("supervisor@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    incidents = client.get("/api/v1/incidents", headers=headers)
    assert incidents.status_code == 200
    inc_items = api_items(incidents.json())
    if not inc_items:
        return
    iid = inc_items[0]["id"]
    res = client.patch(
        f"/api/v1/incidents/{iid}",
        headers=headers,
        json={"status": "ACTION_TAKEN"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ACTION_TAKEN"


def test_attachment_share_with_parent():
    token = _login("casemanager@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    case_id = api_items(cases.json())[0]["id"]
    attachments = client.get(f"/api/v1/attachments?case_id={case_id}", headers=headers)
    if attachments.status_code != 200 or not attachments.json():
        return
    aid = attachments.json()[0]["id"]
    res = client.patch(
        f"/api/v1/attachments/{aid}",
        headers=headers,
        json={"visibility_status": "APPROVED_FOR_PARENT"},
    )
    assert res.status_code == 200
    assert res.json()["visibility_status"] == "APPROVED_FOR_PARENT"


def test_report_detail_endpoint():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    reports = client.get("/api/v1/reports/monthly", headers=headers)
    assert reports.status_code == 200
    report_items = api_items(reports.json())
    assert report_items
    rid = report_items[0]["id"]
    detail = client.get(f"/api/v1/reports/monthly/{rid}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == rid


def test_case_code_preview_and_generation():
    token = _login("casemanager@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    preview = client.get(
        "/api/v1/admin/cases/next-code?product_module=homecare",
        headers=headers,
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["case_code"].startswith("IC-")
    assert "-HC-" in body["case_code"]
    assert "HC" in body["preview"]


def test_create_case_without_manual_code():
    token = _login("casemanager@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    child_id = api_items(cases.json())[0]["child_id"]

    res = client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "child_id": child_id,
            "service_type": "Test service",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_rate_per_session_inr": 1000,
            "pay_share_pct": 60,
        },
    )
    assert res.status_code == 201, res.text
    code = res.json()["case_code"]
    assert code.startswith("IC-") and "-HC-" in code


def test_admin_create_child_and_family():
    import uuid

    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:8]
    child = client.post(
        "/api/v1/admin/children",
        headers=headers,
        json={"first_name": "Test", "last_name": f"Child{suffix}"},
    )
    assert child.status_code == 201
    assert child.json()["id"]

    fam = client.post(
        "/api/v1/admin/families",
        headers=headers,
        json={
            "parent_email": f"parent-{suffix}@demo.com",
            "parent_full_name": "Test Parent",
            "child": {"first_name": "New", "last_name": f"Kid{suffix}"},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201
    assert fam.json()["childId"]


def test_allotment_therapists_and_allot_case():
    import uuid

    token = _login("casemanager@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare&approved_only=false",
        headers=headers,
    )
    assert therapists.status_code == 200
    assert therapists.json()
    therapist_id = therapists.json()[0]["therapist_user_id"]

    admin_token = _login("superadmin@demo.com")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    suffix = uuid.uuid4().hex[:8]
    child = client.post(
        "/api/v1/admin/children",
        headers=admin_headers,
        json={"first_name": "Allot", "last_name": suffix},
    )
    assert child.status_code == 201
    child_id = child.json()["id"]

    allot = client.post(
        "/api/v1/admin/cases/allot",
        headers=headers,
        json={
            "child_id": child_id,
            "service_type": "Homecare",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_pct": 60,
            "therapist_user_id": therapist_id,
        },
    )
    assert allot.status_code == 201, allot.text
    assert allot.json()["case"]["status"] == "ACTIVE"
    assert allot.json()["assignment_id"]


def test_admin_iep_dashboard():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    dash = client.get("/api/v1/admin/iep/dashboard", headers=headers)
    assert dash.status_code == 200
    body = dash.json()
    assert "summary" in body
    assert "rows" in body
    assert body["summary"]["total_cases"] >= 0
    filtered = client.get("/api/v1/admin/iep/dashboard?status=MISSING", headers=headers)
    assert filtered.status_code == 200
    for row in filtered.json()["rows"]:
        assert row["iep_status"] == "MISSING"


def test_admin_cases_pipeline_board():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    board = client.get("/api/v1/admin/cases/pipeline", headers=headers)
    assert board.status_code == 200
    body = board.json()
    assert "columns" in body
    assert body["total_cases"] >= 0
    col_ids = {c["id"] for c in body["columns"]}
    assert "pending_allotment" in col_ids
    assert "reports_logs" in col_ids


def test_admin_list_invites():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    invites = client.get("/api/v1/admin/invites", headers=headers)
    assert invites.status_code == 200
    assert isinstance(invites.json(), list)


def test_therapist_onboard_invite_and_accept():
    import uuid

    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    email = f"onboard-{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/api/v1/admin/therapists/onboard",
        headers=headers,
        json={
            "email": email,
            "full_name": "Onboard Test",
            "phone": "555-0199",
            "mode": "invite",
            "services_offered": ["shadow", "homecare"],
            "module_assignments": ["homecare", "shadow_support"],
            "send_email": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("invite_url")
    token_str = body["invite_url"].rstrip("/").split("/")[-1]
    accept = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": token_str, "password": "demo12345", "full_name": "Onboard Test"},
    )
    assert accept.status_code == 200, accept.text
    profiles = client.get("/api/v1/admin/therapist-profiles", headers=headers)
    assert profiles.status_code == 200
    match = [p for p in profiles.json() if p.get("email") == email]
    assert match, "Therapist profile should exist after invite accept"
    assert match[0]["status"] == "APPROVED"
    assert "shadow" in (match[0].get("services_offered") or [])


def test_admin_reports_summary_and_queue():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    summary = client.get("/api/v1/admin/reports/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert "monthly" in body
    assert "observation" in body
    assert "queue_total" in body

    queue = client.get("/api/v1/admin/reports/queue?page_size=10", headers=headers)
    assert queue.status_code == 200, queue.text
    assert "items" in queue.json()


def test_admin_reports_case_filter_and_exports():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    case_id = api_items(cases.json())[0]["id"]

    monthly = client.get(
        f"/api/v1/admin/reports/monthly?case_id={case_id}&page_size=5",
        headers=headers,
    )
    assert monthly.status_code == 200, monthly.text
    for item in monthly.json().get("items", []):
        assert item["case_id"] == case_id

    xlsx = client.get("/api/v1/admin/reports/export/xlsx?queue_only=true", headers=headers)
    assert xlsx.status_code == 200
    assert "spreadsheetml" in xlsx.headers.get("content-type", "")

    pdf = client.get("/api/v1/admin/reports/export/pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.headers.get("content-type", "").startswith("application/pdf")


def test_admin_reports_bulk_approve_reject():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    queue = client.get("/api/v1/admin/reports/queue?type=monthly&page_size=5", headers=headers)
    assert queue.status_code == 200
    items = queue.json().get("items", [])
    under_review = [i for i in items if i["status"] == "UNDER_REVIEW" and i["report_type"] == "monthly"]
    if not under_review:
        return
    rid = under_review[0]["id"]
    reject = client.post(
        "/api/v1/admin/reports/bulk/reject",
        headers=headers,
        json={"report_type": "monthly", "ids": [rid], "comment": "Test rejection"},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["succeeded"] >= 1

    detail = client.get(f"/api/v1/admin/reports/monthly/{rid}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "REJECTED"


def test_observation_reports_list():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/api/v1/reports/observation", headers=headers)
    assert listed.status_code == 200
    assert "items" in listed.json()


def test_admin_families_search_and_link_by_email():
    import uuid

    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:8]
    child = client.post(
        "/api/v1/admin/children",
        headers=headers,
        json={"first_name": "Orphan", "last_name": suffix},
    )
    assert child.status_code == 201
    child_id = child.json()["id"]

    listed = client.get("/api/v1/admin/families?search=Orphan", headers=headers)
    assert listed.status_code == 200
    assert any(r.get("childId") == child_id for r in listed.json())

    link = client.post(
        f"/api/v1/admin/families/link-by-email?child_id={child_id}&parent_email=link-{suffix}@demo.com",
        headers=headers,
    )
    assert link.status_code == 200, link.text


def test_cm_meetings_filters_and_case_code():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get(
        "/api/v1/cm-meetings?meeting_type=SUPERVISION&status=SCHEDULED",
        headers=headers,
    )
    assert listed.status_code == 200
    items = listed.json()
    assert isinstance(items, list)
    for row in items:
        assert row.get("meeting_type") == "SUPERVISION"
        if row.get("case_id"):
            assert row.get("case_code")


def test_ticket_assign_patch_and_internal_note():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    tickets = client.get("/api/v1/tickets?page_size=5", headers=headers)
    assert tickets.status_code == 200
    items = api_items(tickets.json())
    if not items:
        return
    tid = items[0]["id"]
    cm_token = _login("casemanager@demo.com")
    cm_headers = {"Authorization": f"Bearer {cm_token}"}
    cm_id = client.get("/api/v1/auth/me", headers=cm_headers).json()["id"]
    patched = client.patch(
        f"/api/v1/tickets/{tid}",
        headers=headers,
        json={"assigned_to_user_id": cm_id},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json().get("assigned_to_name")

    msg = client.post(
        f"/api/v1/tickets/{tid}/messages",
        headers=headers,
        json={"body": "Internal staff note", "is_internal": True},
    )
    assert msg.status_code == 201, msg.text


def test_incident_create_auto_assigns():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    case_id = api_items(cases.json())[0]["id"]
    res = client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "case_id": case_id,
            "primary_category": "SESSION_CLASSROOM_PROGRAM",
            "subcategory": "session_disrupted",
            "what_happened": "Auto-assign check for incident routing.",
            "is_sensitive": False,
        },
    )
    assert res.status_code == 201, res.text
    detail = client.get(f"/api/v1/incidents/{res.json()['id']}", headers={"Authorization": f"Bearer {_login('superadmin@demo.com')}"})
    assert detail.status_code == 200
    assert detail.json().get("assigned_to_user_id") or detail.json().get("assigned_to_name")


def test_workbench_summary_scoped():
    cm_token = _login("casemanager@demo.com")
    cm_headers = {"Authorization": f"Bearer {cm_token}"}
    wb = client.get("/api/v1/admin/workbench/summary", headers=cm_headers)
    assert wb.status_code == 200, wb.text
    assert "sections" in wb.json()


def test_viewer_cannot_patch_case():
    token = _login("viewer@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    case_id = api_items(cases.json())[0]["id"]
    patch = client.patch(
        f"/api/v1/cases/{case_id}",
        headers=headers,
        json={"status": "SUSPENDED"},
    )
    assert patch.status_code == 403


def test_supervisor_can_list_cm_meetings():
    token = _login("supervisor@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/api/v1/cm-meetings", headers=headers)
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)


def test_therapist_profiles_summary():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    summary = client.get("/api/v1/admin/therapist-profiles/summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert "PENDING" in body
    assert "no_profile" in body


def test_workbench_includes_reschedules_section():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    wb = client.get("/api/v1/admin/workbench/summary", headers=headers)
    assert wb.status_code == 200, wb.text
    sections = wb.json().get("sections", {})
    assert "reschedules" in sections
    assert "count" in sections["reschedules"]
    assert "items" in sections["reschedules"]


def test_pipeline_assign_moves_case_from_needs_therapist():
    admin_token = _login("superadmin@demo.com")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    pipeline = client.get("/api/v1/admin/cases/pipeline", headers=admin_headers)
    assert pipeline.status_code == 200
    needs_col = next((c for c in pipeline.json()["columns"] if c["id"] == "needs_therapist"), None)
    if not needs_col or not needs_col["cases"]:
        cases = client.get("/api/v1/cases?status=ACTIVE", headers=admin_headers)
        active = api_items(cases.json())
        case_id = active[0]["id"] if active else None
        if not case_id:
            pytest.skip("No case for assignment test")
    else:
        case_id = needs_col["cases"][0]["id"]

    case_detail = client.get(f"/api/v1/cases/{case_id}", headers=admin_headers)
    assert case_detail.status_code == 200
    product_module = case_detail.json().get("product_module") or "homecare"

    th_list = client.get(
        f"/api/v1/admin/allotment/therapists?product_module={product_module}",
        headers=admin_headers,
    )
    assert th_list.status_code == 200, th_list.text
    th_rows = th_list.json() if isinstance(th_list.json(), list) else api_items(th_list.json())
    if not th_rows:
        pytest.skip("No therapists in seed")
    first = th_rows[0]
    tid = first.get("therapist_user_id") or first.get("user_id") or first.get("id")

    assign = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=admin_headers,
        json={
            "therapist_user_id": tid,
            "start_date": "2026-06-01",
            "reason_for_change": "Pipeline test assign",
        },
    )
    assert assign.status_code == 201, assign.text

    pipeline2 = client.get("/api/v1/admin/cases/pipeline", headers=admin_headers)
    assert pipeline2.status_code == 200
    all_ids = {c["id"] for col in pipeline2.json()["columns"] for c in col["cases"]}
    assert case_id in all_ids


def test_report_categories_endpoint():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/v1/reports/categories", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "categories" in body
    ids = {c["id"] for c in body["categories"]}
    assert "CLIENT_MONTHLY" in ids
    assert "IEP_PLAN" in ids


def test_admin_missing_monthly_reports():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/v1/admin/reports/missing-monthly?month=January%209900", headers=headers)
    assert res.status_code == 200, res.text
    assert isinstance(res.json(), list)
