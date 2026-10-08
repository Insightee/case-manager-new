"""Parent portal API tests."""

from datetime import date

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parent_session_logs_visibility():
    headers = _login("parent@demo.com")
    logs = client.get("/api/v1/parent/session-logs", headers=headers)
    assert logs.status_code == 200
    data = logs.json()
    assert isinstance(data, list)
    if data:
        assert "parent_notes" in data[0] or "activities_done" in data[0]
        assert "session_notes" not in data[0]


def test_parent_cases_enriched():
    headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    assert len(cases) >= 1
    c = cases[0]
    assert "therapistName" in c
    assert "latestApprovedReportMonth" in c
    for row in cases:
        assert row["status"] in ("ACTIVE", "PENDING_ALLOTMENT")


def test_parent_cases_hide_closed_and_suspended():
    import uuid

    suffix = uuid.uuid4().hex[:8]
    parent_email = f"closed-case-{suffix}@demo.com"
    parent_password = "demo123"
    admin_headers = _login("superadmin@demo.com")

    fam = client.post(
        "/api/v1/admin/families",
        headers=admin_headers,
        json={
            "parent_email": parent_email,
            "parent_full_name": "Closed Case Parent",
            "child": {"first_name": "Closed", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]
    parent_user_id = fam.json()["parentUserId"]

    pwd = client.post(
        f"/api/v1/admin/users/{parent_user_id}/set-password",
        headers=admin_headers,
        json={"password": parent_password},
    )
    assert pwd.status_code == 200, pwd.text

    therapists = client.get("/api/v1/admin/users/directory?roles=THERAPIST", headers=admin_headers)
    assert therapists.status_code == 200, therapists.text
    therapist_rows = therapists.json()
    assert therapist_rows, "seed should include at least one therapist"
    therapist_id = therapist_rows[0]["id"]

    allot = client.post(
        "/api/v1/admin/cases/allot",
        headers=admin_headers,
        json={
            "child_id": child_id,
            "service_type": "Shadow support",
            "product_module": "shadow_support",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_amount_inr": 720,
            "therapist_user_id": therapist_id,
            "day_type": "HALF_DAY",
        },
    )
    assert allot.status_code == 201, allot.text
    case_id = allot.json()["case"]["id"]

    activate = client.post(
        f"/api/v1/admin/cases/{case_id}/activate-allotment",
        headers=admin_headers,
    )
    assert activate.status_code == 200, activate.text

    # Second active case keeps parent portal login after the first case closes.
    allot_b = client.post(
        "/api/v1/admin/cases/allot",
        headers=admin_headers,
        json={
            "child_id": child_id,
            "service_type": "Shadow support",
            "product_module": "shadow_support",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 900,
            "pay_share_amount_inr": 540,
            "therapist_user_id": therapist_id,
            "day_type": "HALF_DAY",
        },
    )
    assert allot_b.status_code == 201, allot_b.text
    case_id_b = allot_b.json()["case"]["id"]
    activate_b = client.post(
        f"/api/v1/admin/cases/{case_id_b}/activate-allotment",
        headers=admin_headers,
    )
    assert activate_b.status_code == 200, activate_b.text

    parent = _login(parent_email, parent_password)
    visible_before = client.get("/api/v1/parent/cases", headers=parent).json()
    assert any(row["id"] == case_id for row in visible_before)
    assert any(row["id"] == case_id_b for row in visible_before)

    close = client.post(
        f"/api/v1/cases/{case_id}/client-status",
        headers=admin_headers,
        json={
            "new_status": "CLOSED",
            "effective_date": date.today().isoformat(),
            "reason": "Test close for parent portal visibility",
        },
    )
    assert close.status_code == 200, close.text

    visible = client.get("/api/v1/parent/cases", headers=parent).json()
    assert all(row["id"] != case_id for row in visible)
    assert any(row["id"] == case_id_b for row in visible)

    home = client.get("/api/v1/parent/home", headers=parent).json()
    assert all(row["id"] != case_id for row in home["cases"])
    assert any(row["id"] == case_id_b for row in home["cases"])
    assert home["stats"]["case_count"] == len(visible)

    detail = client.get(f"/api/v1/parent/cases/{case_id}", headers=parent)
    assert detail.status_code == 404

    # DEC-02: SUSPENDED cases are also hidden from parent portal (PENDING_REPLACEMENT stays visible).
    suspend_b = client.post(
        f"/api/v1/cases/{case_id_b}/client-status",
        headers=admin_headers,
        json={
            "new_status": "SUSPENDED",
            "effective_date": date.today().isoformat(),
            "reason": "Test suspend for parent portal visibility",
        },
    )
    assert suspend_b.status_code == 200, suspend_b.text
    visible_after_suspend = client.get("/api/v1/parent/cases", headers=parent).json()
    assert all(row["id"] != case_id_b for row in visible_after_suspend)
    detail_b = client.get(f"/api/v1/parent/cases/{case_id_b}", headers=parent)
    assert detail_b.status_code == 404

    # PENDING_REPLACEMENT remains accessible to the family.
    reopen = client.post(
        f"/api/v1/cases/{case_id_b}/client-status",
        headers=admin_headers,
        json={
            "new_status": "ACTIVE",
            "effective_date": date.today().isoformat(),
            "reason": "Reactivate before replacement status",
        },
    )
    assert reopen.status_code == 200, reopen.text
    replace = client.post(
        f"/api/v1/cases/{case_id_b}/client-status",
        headers=admin_headers,
        json={
            "new_status": "PENDING_REPLACEMENT",
            "effective_date": date.today().isoformat(),
            "reason": "Waiting for new therapist",
        },
    )
    assert replace.status_code == 200, replace.text
    visible_replace = client.get("/api/v1/parent/cases", headers=parent).json()
    assert any(row["id"] == case_id_b for row in visible_replace)


def test_parent_report_detail_and_other_family_denied():
    parent_h = _login("parent@demo.com")
    reports = client.get("/api/v1/parent/reports", headers=parent_h).json()
    if not reports:
        return
    rid = reports[0]["id"]
    detail = client.get(f"/api/v1/parent/reports/{rid}", headers=parent_h)
    assert detail.status_code == 200
    assert detail.json()["summary"]


def test_parent_iep_acknowledge():
    headers = _login("parent@demo.com")
    items = client.get("/api/v1/parent/iep-status", headers=headers).json()
    pending = [i for i in items if i["status"] == "pending"]
    if not pending:
        return
    att_id = pending[0]["id"]
    r = client.post(f"/api/v1/parent/iep/{att_id}/acknowledge", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"


def test_parent_billing_summaries():
    headers = _login("parent@demo.com")
    rows = client.get("/api/v1/parent/billing-summaries", headers=headers).json()
    assert isinstance(rows, list)


def test_parent_profile_get_and_update():
    headers = _login("parent@demo.com")
    r = client.get("/api/v1/parent/profile", headers=headers)
    assert r.status_code == 200
    profile = r.json()
    assert profile["full_name"]
    assert profile["email"]
    assert "children" in profile
    assert "services" in profile

    patch = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={"phone": "9876543210", "full_name": profile["full_name"]},
    )
    assert patch.status_code == 200
    assert patch.json()["phone"] == "9876543210"


def test_parent_profile_email_cannot_be_changed():
    headers = _login("parent@demo.com")
    profile = client.get("/api/v1/parent/profile", headers=headers).json()
    original_email = profile["email"]

    # Email field removed from schema — extra field is ignored; login email stays the same
    patch = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={"email": "hacker@example.com", "full_name": profile["full_name"]},
    )
    assert patch.status_code == 200
    assert patch.json()["email"] == original_email

    again = client.get("/api/v1/parent/profile", headers=headers).json()
    assert again["email"] == original_email


def test_parent_profile_secondary_contact():
    headers = _login("parent@demo.com")
    profile = client.get("/api/v1/parent/profile", headers=headers).json()

    patch = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={
            "full_name": profile["full_name"],
            "secondary_contact_name": "Spouse Name",
            "secondary_contact_email": "spouse@example.com",
        },
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["secondary_contact_name"] == "Spouse Name"
    assert body["secondary_contact_email"] == "spouse@example.com"


def test_parent_change_password():
    headers = _login("parent@demo.com")
    bad = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "wrong", "new_password": "newpass7890"},
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "demo123", "new_password": "newpass789"},
    )
    assert ok.status_code == 200, ok.text

    login_new = client.post(
        "/api/v1/auth/login",
        json={"email": "parent@demo.com", "password": "newpass789"},
    )
    assert login_new.status_code == 200, login_new.text

    admin_headers = _login("superadmin@demo.com")
    restore = client.post(
        f"/api/v1/admin/users/{client.get('/api/v1/auth/me', headers=headers).json()['id']}/set-password",
        headers=admin_headers,
        json={"password": "demo123"},
    )
    assert restore.status_code == 200, restore.text


def test_parent_profile_email_preferences():
    headers = _login("parent@demo.com")
    profile = client.get("/api/v1/parent/profile", headers=headers).json()
    prefs = profile.get("email_preferences") or {}
    assert prefs.get("session_logs") is True
    assert prefs.get("billing") is True
    assert prefs.get("meetings") is True
    assert profile.get("receive_log_leave_emails") is True

    off = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={
            "full_name": profile["full_name"],
            "email_preferences": {
                "appointments": False,
                "session_logs": False,
                "therapist_leave": False,
                "billing": False,
                "reports": False,
                "meetings": False,
            },
        },
    )
    assert off.status_code == 200, off.text
    body = off.json()
    assert body["email_preferences"]["appointments"] is False
    assert body["email_preferences"]["session_logs"] is False
    assert body["receive_log_leave_emails"] is False

    partial = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={
            "full_name": profile["full_name"],
            "email_preferences": {"appointments": True},
        },
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["email_preferences"]["appointments"] is True
    assert partial.json()["email_preferences"]["billing"] is False

    legacy = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={"full_name": profile["full_name"], "receive_log_leave_emails": True},
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["receive_log_leave_emails"] is True
    assert legacy.json()["email_preferences"]["session_logs"] is True
    assert legacy.json()["email_preferences"]["therapist_leave"] is True


def test_parent_profile_log_leave_email_preference_legacy_field():
    headers = _login("parent@demo.com")
    profile = client.get("/api/v1/parent/profile", headers=headers).json()
    assert profile.get("receive_log_leave_emails") is True

    off = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={"full_name": profile["full_name"], "receive_log_leave_emails": False},
    )
    assert off.status_code == 200, off.text
    assert off.json()["receive_log_leave_emails"] is False

    on = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={"full_name": profile["full_name"], "receive_log_leave_emails": True},
    )
    assert on.status_code == 200, on.text
    assert on.json()["receive_log_leave_emails"] is True


def test_parent_profile_home_and_school_addresses_are_separate():
    headers = _login("parent@demo.com")
    r = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={
            "home_address_line1": "10 Home Street",
            "home_city": "Bangalore",
            "home_pincode": "560001",
            "school_address_line1": "42 School Road",
            "school_city": "Bangalore",
            "school_pincode": "560034",
            "address_type": "school",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["home_address"]["address_line1"] == "10 Home Street"
    assert body["school_address"]["address_line1"] == "42 School Road"
    assert body["address_type"] == "school"

    r2 = client.patch(
        "/api/v1/parent/profile",
        headers=headers,
        json={
            "school_address_line1": "99 Updated School Campus",
            "school_city": "Bangalore",
            "school_pincode": "560034",
        },
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["school_address"]["address_line1"] == "99 Updated School Campus"
    assert body2["home_address"]["address_line1"] == "10 Home Street"


def test_parent_reports_hub():
    headers = _login("parent@demo.com")
    hub = client.get("/api/v1/parent/reports/hub", headers=headers)
    assert hub.status_code == 200
    data = hub.json()
    assert "monthly" in data
    assert "iep" in data
    assert isinstance(data["items"], list)


def test_parent_monthly_feedback_returns_under_review():
    admin_h = _login("superadmin@demo.com")
    parent_h = _login("parent@demo.com")
    hub = client.get("/api/v1/parent/reports/hub", headers=parent_h).json()
    pending = [
        m
        for m in hub.get("monthly", [])
        if m.get("parentReviewStatus") == "PENDING" or m.get("status") == "pending_review"
    ]
    if not pending:
        return
    rid = pending[0]["id"]
    fb = client.post(
        f"/api/v1/parent/reports/monthly/{rid}/feedback",
        headers=parent_h,
        json={"message": "Please update goals section"},
    )
    assert fb.status_code == 200
    assert fb.json()["parentReviewStatus"] == "CHANGES_REQUESTED"
    detail = client.get(f"/api/v1/reports/monthly/{rid}", headers=admin_h)
    assert detail.status_code == 200
    assert detail.json()["status"] == "UNDER_REVIEW"


def test_parent_monthly_approve():
    parent_h = _login("parent@demo.com")
    hub = client.get("/api/v1/parent/reports/hub", headers=parent_h).json()
    pending = [
        m
        for m in hub.get("monthly", [])
        if m.get("parentReviewStatus") == "PENDING" or m.get("status") == "pending_review"
    ]
    if not pending:
        return
    rid = pending[0]["id"]
    r = client.post(f"/api/v1/parent/reports/monthly/{rid}/approve", headers=parent_h)
    assert r.status_code == 200
    assert r.json()["parentReviewStatus"] == "APPROVED"


def test_parent_monthly_detail_and_download():
    parent_h = _login("parent@demo.com")
    hub = client.get("/api/v1/parent/reports/hub", headers=parent_h).json()
    if not hub.get("monthly"):
        return
    rid = hub["monthly"][0]["id"]
    detail = client.get(f"/api/v1/parent/reports/monthly/{rid}", headers=parent_h)
    assert detail.status_code == 200
    data = detail.json()
    assert data.get("kind") == "monthly"
    assert data.get("summary") or data.get("bodyHtml")
    assert data.get("downloadPath", "").startswith("/api/v1/parent/reports/monthly/")
    pdf = client.get(data["downloadPath"], headers=parent_h)
    assert pdf.status_code == 200
    assert pdf.headers.get("content-type", "").startswith("application/pdf")


def test_parent_iep_comment_create():
    parent_h = _login("parent@demo.com")
    hub = client.get("/api/v1/parent/reports/hub", headers=parent_h).json()
    if not hub.get("iep"):
        return
    att_id = hub["iep"][0]["id"]
    r = client.post(
        f"/api/v1/parent/reports/iep/{att_id}/comments",
        headers=parent_h,
        json={"body": "Consider adding a communication goal", "comment_type": "GOAL_SUGGESTION"},
    )
    assert r.status_code == 200
    detail = client.get(f"/api/v1/parent/reports/iep/{att_id}", headers=parent_h)
    assert detail.status_code == 200
    assert len(detail.json().get("comments", [])) >= 1


def test_parent_booking_availability():
    headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=headers)
    assert cases.status_code == 200
    case_list = cases.json()
    if not case_list:
        return
    case_id = case_list[0]["id"]
    therapists = client.get(f"/api/v1/booking/therapists?case_id={case_id}", headers=headers)
    assert therapists.status_code == 200, therapists.text
    tlist = therapists.json()
    if not tlist:
        return
    tid = tlist[0]["therapist_user_id"]
    from datetime import date, timedelta

    day = (date.today() + timedelta(days=7)).isoformat()
    avail = client.get(
        f"/api/v1/booking/availability?therapist_id={tid}&from_date={day}&to_date={day}",
        headers=headers,
    )
    assert avail.status_code == 200, avail.text
    assert isinstance(avail.json(), list)
