"""Integration API security, masking, scopes, grants, and audit tests."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.case import Case
from app.models.integration import IntegrationCredential
from app.models.report import MonthlyReport, ReportStatus
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import User
from app.services.integration.rate_limit import reset_memory_rate_limits_for_tests
from app.tests.conftest import login_headers


@pytest.fixture(autouse=True)
def _enable_integration(monkeypatch):
    monkeypatch.setattr(settings, "integration_api_enabled", True)
    monkeypatch.setattr(settings, "mcp_enabled", True)
    reset_memory_rate_limits_for_tests()
    yield
    reset_memory_rate_limits_for_tests()


@pytest.fixture
def client():
    # Context manager is required so FastAPI lifespan starts the MCP session manager.
    with TestClient(app) as test_client:
        yield test_client


def _first_case_and_report(db):
    case = db.scalars(select(Case).order_by(Case.id).limit(1)).first()
    assert case is not None
    report = db.scalars(
        select(MonthlyReport).where(MonthlyReport.case_id == case.id).order_by(MonthlyReport.id).limit(1)
    ).first()
    return case, report


def _create_integration_client(client, admin_headers, *, scopes, case_ids):
    res = client.post(
        "/api/v1/admin/integration-clients",
        headers=admin_headers,
        json={"name": "Test Partner", "scopes": scopes, "case_ids": case_ids},
    )
    assert res.status_code == 201, res.text
    return res.json()


def _token(client, client_id: str, client_secret: str):
    res = client.post(
        "/api/v1/integrations/oauth/token",
        json={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    return res


def test_token_auth_failure(client):
    res = _token(client, "ic_missing", "wrong-secret")
    assert res.status_code == 401
    body = res.json()["detail"]
    assert body["code"] == "unauthorized"


def test_missing_scope_forbidden(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        case, _ = _first_case_and_report(db)
        case_id = case.id
    finally:
        db.close()
    created = _create_integration_client(
        client, admin, scopes=["ops:summary"], case_ids=[case_id]
    )
    tok = _token(client, created["client_id"], created["client_secret"])
    assert tok.status_code == 200
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    res = client.get("/api/v1/integrations/v1/cases", headers=headers)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "forbidden"


def test_cross_case_access_denied(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        cases = list(db.scalars(select(Case).order_by(Case.id).limit(2)).all())
        assert len(cases) >= 2
        granted, other = cases[0].id, cases[1].id
    finally:
        db.close()
    created = _create_integration_client(
        client, admin, scopes=["cases:read", "reports:read"], case_ids=[granted]
    )
    tok = _token(client, created["client_id"], created["client_secret"])
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    ok = client.get(f"/api/v1/integrations/v1/cases/{granted}", headers=headers)
    assert ok.status_code == 200
    denied = client.get(f"/api/v1/integrations/v1/cases/{other}", headers=headers)
    assert denied.status_code == 404
    assert denied.json()["detail"]["code"] == "not_found"


def test_therapist_cannot_manage_integration_clients(client):
    th = login_headers(client, "therapist@demo.com")
    res = client.post(
        "/api/v1/admin/integration-clients",
        headers=th,
        json={"name": "Nope", "scopes": ["ops:summary"], "case_ids": []},
    )
    assert res.status_code == 403


def test_case_manager_cannot_manage_integration_clients(client):
    cm = login_headers(client, "casemanager@demo.com")
    res = client.get("/api/v1/admin/integration-clients", headers=cm)
    assert res.status_code == 403


def test_admin_can_manage_and_masking(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        case, report = _first_case_and_report(db)
        case_id = case.id
        if report is None:
            from app.models.user import User

            therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
            assert therapist is not None
            report = MonthlyReport(
                case_id=case_id,
                therapist_user_id=therapist.id,
                month="2099-01",
                status=ReportStatus.UNDER_REVIEW,
                summary="Sensitive clinical narrative for masking test",
                body_html="<p>INTERNAL BODY</p>",
            )
            db.add(report)
            db.commit()
            db.refresh(report)
        report_id = report.id
        # Ensure sensitive fields exist for masking assertions
        report.body_html = "<p>SECRET_HTML</p>"
        report.summary = "Child full clinical detail should not leak"
        db.commit()
    finally:
        db.close()

    created = _create_integration_client(
        client,
        admin,
        scopes=["cases:read", "reports:read", "sessions:summarize", "reporting:pending", "ops:summary"],
        case_ids=[case_id],
    )
    tok = _token(client, created["client_id"], created["client_secret"])
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}

    case_res = client.get(f"/api/v1/integrations/v1/cases/{case_id}", headers=headers)
    assert case_res.status_code == 200, case_res.text
    case_body = case_res.json()
    assert "child_initials" in case_body
    assert "date_of_birth" not in case_body
    assert "first_name" not in case_body
    assert "email" not in case_body
    assert "service_address_line1" not in case_body

    rep = client.get(
        f"/api/v1/integrations/v1/reports/{report_id}?report_type=monthly",
        headers=headers,
    )
    assert rep.status_code == 200, rep.text
    rep_body = rep.json()
    assert "body_html" not in rep_body
    assert "SECRET_HTML" not in str(rep_body)
    assert rep_body.get("summary_excerpt") is None or "SECRET_HTML" not in rep_body["summary_excerpt"]

    sess = client.get(f"/api/v1/integrations/v1/cases/{case_id}/session-summary", headers=headers)
    assert sess.status_code == 200
    assert "checkin_lat" not in sess.json()

    ops = client.get("/api/v1/integrations/v1/ops/summary", headers=headers)
    assert ops.status_code == 200
    assert "granted_case_count" in ops.json()


def test_pagination_max_page_size(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        case_id = db.scalars(select(Case.id).limit(1)).first()
    finally:
        db.close()
    created = _create_integration_client(
        client, admin, scopes=["cases:read"], case_ids=[case_id]
    )
    tok = _token(client, created["client_id"], created["client_secret"])
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    res = client.get("/api/v1/integrations/v1/cases?page_size=500", headers=headers)
    assert res.status_code == 200
    assert res.json()["page_size"] <= settings.integration_max_page_size


def test_audit_log_created_without_secrets(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        case_id = db.scalars(select(Case.id).limit(1)).first()
    finally:
        db.close()
    created = _create_integration_client(
        client, admin, scopes=["cases:read"], case_ids=[case_id]
    )
    secret = created["client_secret"]
    tok = _token(client, created["client_id"], secret)
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    client.get(f"/api/v1/integrations/v1/cases/{case_id}", headers=headers)

    db = SessionLocal()
    try:
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.action.in_(["integration.token_issued", "integration.case_read"]))
                .order_by(AuditEvent.id.desc())
                .limit(10)
            ).all()
        )
        assert any(e.action == "integration.token_issued" for e in events)
        assert any(e.action == "integration.case_read" for e in events)
        for e in events:
            blob = f"{e.old_value or ''}{e.new_value or ''}"
            assert secret not in blob
            assert "Bearer" not in blob
            assert e.integration_client_id is not None
    finally:
        db.close()


def test_revoked_credential_rejected(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        case_id = db.scalars(select(Case.id).limit(1)).first()
    finally:
        db.close()
    created = _create_integration_client(
        client, admin, scopes=["cases:read"], case_ids=[case_id]
    )
    tok = _token(client, created["client_id"], created["client_secret"])
    assert tok.status_code == 200
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}

    revoke = client.post(
        f"/api/v1/admin/integration-clients/{created['id']}/revoke",
        headers=admin,
    )
    assert revoke.status_code == 200

    # Existing access token must fail because credential is revoked
    res = client.get("/api/v1/integrations/v1/cases", headers=headers)
    assert res.status_code == 401

    # New token issuance also fails
    again = _token(client, created["client_id"], created["client_secret"])
    assert again.status_code == 401


def test_expired_credential_rejected(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        case_id = db.scalars(select(Case.id).limit(1)).first()
    finally:
        db.close()
    created = _create_integration_client(
        client, admin, scopes=["cases:read"], case_ids=[case_id]
    )

    db = SessionLocal()
    try:
        cred = db.scalars(
            select(IntegrationCredential).where(
                IntegrationCredential.public_client_id == created["client_id"]
            )
        ).first()
        cred.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    finally:
        db.close()
    res = _token(client, created["client_id"], created["client_secret"])
    assert res.status_code == 401


def test_mcp_layer_has_no_sqlalchemy_session_usage():
    mcp_root = Path(__file__).resolve().parents[1] / "mcp"
    assert mcp_root.is_dir()
    for path in mcp_root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "sqlalchemy" in node.module:
                    pytest.fail(f"{path} imports sqlalchemy: {node.module}")
                if node.module == "app.core.database":
                    pytest.fail(f"{path} must not import app.core.database")
            if isinstance(node, ast.Name) and node.id == "Session":
                # Allow string annotations only if sqlalchemy imported — already blocked
                pass


def test_mcp_tools_registered():
    pytest.importorskip("mcp")
    from app.mcp.server import build_mcp_server
    import asyncio

    server = build_mcp_server()
    tools = asyncio.run(server.list_tools())
    if hasattr(tools, "tools"):
        names = {t.name for t in tools.tools}
    else:
        names = {t.name for t in tools}
    assert "list_authorised_reports" in names
    assert "get_report" in names
    assert "get_case_summary" in names
    assert "get_session_summary" in names
    assert "list_pending_reporting" in names
    assert "get_anonymised_ops_summary" in names
    assert "list_therapist_profiles" in names
    assert "create_therapist_profile" in names


def test_mcp_invalid_inputs_safe_error():
    from app.mcp.server import mcp_public_error
    from app.services.integration.errors import ValidationError, UnauthorizedError

    msg = mcp_public_error(ValidationError("bad"))
    assert "validation_error" in msg
    assert "sqlalchemy" not in msg.lower()
    assert "traceback" not in msg.lower()
    unauth = mcp_public_error(UnauthorizedError())
    assert "unauthorized" in unauth


def test_mcp_http_initialize_and_tools(client):
    """Streamable HTTP MCP must initialize when session manager lifespan is wired."""
    pytest.importorskip("mcp")
    init = client.post(
        "/mcp/",
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
    )
    assert init.status_code == 200, init.text
    body = init.json()
    assert body["result"]["serverInfo"]["name"] == "InsighteCase"

    listed = client.post(
        "/mcp/",
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert listed.status_code == 200, listed.text
    names = {t["name"] for t in listed.json()["result"]["tools"]}
    assert "get_case_summary" in names
    assert "list_authorised_reports" in names


def test_permissions_token_life_webhook_and_signal(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        case, report = _first_case_and_report(db)
        case_id = case.id
        report_id = report.id if report else None
        report_status = report.status if report else None
    finally:
        db.close()

    created = client.post(
        "/api/v1/admin/integration-clients",
        headers=admin,
        json={
            "name": "School agent",
            "allow_read": True,
            "allow_write": True,
            "info_access": ["cases", "sessions", "reports", "goals", "iep", "reporting", "ops"],
            "access_token_minutes": 60,
            "key_ttl_days": 0,
            "mcp_enabled": False,
            "case_ids": [case_id],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["allow_write"] is True
    assert "cases:write" in body["scopes"]
    assert "reports:write" not in body["scopes"]
    assert "goals:read" in body["scopes"]
    assert "iep:read" in body["scopes"]
    assert body["key_expires_at"] is None
    assert body["mcp_enabled"] is False
    assert set(body["info_access"]) == {
        "cases",
        "sessions",
        "reports",
        "goals",
        "iep",
        "reporting",
        "ops",
    }

    tok = _token(client, body["client_id"], body["client_secret"])
    assert tok.status_code == 200, tok.text
    assert tok.json()["expires_in"] == 3600
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}

    goals = client.get("/api/v1/integrations/v1/goals?page_size=1", headers=headers)
    assert goals.status_code == 200, goals.text
    goals_body = goals.json()
    assert "items" in goals_body["goals"]
    assert "total" in goals_body["goals"]
    assert "items" in goals_body["strategies"]
    assert goals_body["goals"]["page_size"] == 1
    assert len(goals_body["goals"]["items"]) <= 1
    for row in goals_body["goals"]["items"]:
        assert "goal_id" in row
        assert "label" in row
    for row in goals_body["strategies"]["items"]:
        assert "linked_goal_card_id" in row
        assert "goal_id" not in row
    iep = client.get("/api/v1/integrations/v1/iep", headers=headers)
    assert iep.status_code == 200, iep.text
    assert "items" in iep.json()["plans"]
    assert "total" in iep.json()["plans"]

    signal = client.post(
        "/api/v1/integrations/v1/signals",
        headers=headers,
        json={"case_id": case_id, "domain": "sessions", "signal_key": "progress_signal", "level": 3},
    )
    assert signal.status_code == 201, signal.text
    assert signal.json()["status"] == "pending_review"

    if report_id is not None:
        db = SessionLocal()
        try:
            fresh = db.get(MonthlyReport, report_id)
            assert fresh.status == report_status
        finally:
            db.close()

    denied = client.post(
        "/api/v1/integrations/v1/signals",
        headers=headers,
        json={"case_id": case_id, "domain": "reports", "signal_key": "complete", "level": 1},
    )
    assert denied.status_code == 422, denied.text
    assert "Cases, Sessions, or Goals" in denied.text

    bad_hook = client.post(
        "/api/v1/admin/integration-webhooks",
        headers=admin,
        json={"integration_client_id": body["id"], "url": "http://example.com/hook", "events": ["session.logged"]},
    )
    assert bad_hook.status_code == 422

    hook = client.post(
        "/api/v1/admin/integration-webhooks",
        headers=admin,
        json={
            "integration_client_id": body["id"],
            "url": "https://partner.example/hooks/insightcase",
            "events": ["session.logged", "incident.reported"],
        },
    )
    assert hook.status_code == 201, hook.text
    assert hook.json()["signing_secret"].startswith("whsec_")
    listed = client.get("/api/v1/admin/integration-webhooks", headers=admin)
    assert listed.status_code == 200
    assert all("signing_secret" not in row for row in listed.json())

    from app.services.integration.access import require_mcp
    from app.services.integration.errors import ForbiddenError

    class _Client:
        mcp_enabled = False

    class _Principal:
        client = _Client()

    with pytest.raises(ForbiddenError):
        require_mcp(_Principal())


def test_human_jwt_cannot_use_integration_routes(client):
    human = login_headers(client, "superadmin@demo.com")
    res = client.get("/api/v1/integrations/v1/cases", headers=human)
    assert res.status_code == 401


def test_integration_therapist_profile_list_and_create(client):
    admin = login_headers(client, "superadmin@demo.com")
    db = SessionLocal()
    try:
        case, report = _first_case_and_report(db)
        case_id = case.id
        report_id = report.id if report else None
        report_status = report.status if report else None
        parent = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        assert parent is not None
        parent_id = parent.id
    finally:
        db.close()

    created_user = client.post(
        "/api/v1/admin/users",
        headers=admin,
        json={
            "email": "website.profile.therapist@demo.com",
            "password": "demo123",
            "full_name": "Website Listing Therapist",
            "role_names": ["THERAPIST"],
            "module_assignments": ["homecare"],
        },
    )
    assert created_user.status_code in (201, 400), created_user.text
    if created_user.status_code == 201:
        therapist_id = created_user.json()["id"]
    else:
        db = SessionLocal()
        try:
            row = db.scalars(select(User).where(User.email == "website.profile.therapist@demo.com")).first()
            assert row is not None
            therapist_id = row.id
        finally:
            db.close()

    read_only = _create_integration_client(
        client,
        admin,
        scopes=["cases:read"],
        case_ids=[case_id],
    )
    denied_headers = {"Authorization": f"Bearer {_token(client, read_only['client_id'], read_only['client_secret']).json()['access_token']}"}
    missing = client.get("/api/v1/integrations/v1/therapist-profiles", headers=denied_headers)
    assert missing.status_code == 403, missing.text

    website = client.post(
        "/api/v1/admin/integration-clients",
        headers=admin,
        json={
            "name": "Website profiles",
            "allow_read": True,
            "allow_write": True,
            "info_access": ["profiles"],
            "access_token_minutes": 60,
            "key_ttl_days": 90,
            "mcp_enabled": True,
            "case_ids": [],
        },
    )
    assert website.status_code == 201, website.text
    body = website.json()
    assert "profiles:read" in body["scopes"]
    assert "profiles:write" in body["scopes"]
    assert "reports:write" not in body["scopes"]
    tok = _token(client, body["client_id"], body["client_secret"])
    assert tok.status_code == 200, tok.text
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}

    listed = client.get("/api/v1/integrations/v1/therapist-profiles", headers=headers)
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert "items" in page
    assert page["items"]
    sample = page["items"][0]
    assert "display_name" in sample
    assert "email" not in sample
    assert "tds_rate_percent" not in sample
    assert "leave_balance_year" not in sample
    assert "approved_snapshot" not in sample

    not_therapist = client.post(
        "/api/v1/integrations/v1/therapist-profiles",
        headers=headers,
        json={"user_id": parent_id, "display_name": "Parent"},
    )
    assert not_therapist.status_code == 422, not_therapist.text

    created = client.post(
        "/api/v1/integrations/v1/therapist-profiles",
        headers=headers,
        json={
            "user_id": therapist_id,
            "display_name": "Website Listing Therapist",
            "short_bio": "Supports participation at home.",
            "services_offered": ["homecare"],
            "professional_certificates": ["RCI"],
        },
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert profile["status"] == "PENDING"
    assert profile["user_id"] == therapist_id
    assert profile["services_offered"] == ["homecare"]
    assert "email" not in profile
    assert "leave_paid_days_backfill" not in profile
    assert "admin_note" not in profile

    other_user = client.post(
        "/api/v1/admin/users",
        headers=admin,
        json={
            "email": "website.profile.other@demo.com",
            "password": "demo123",
            "full_name": "Website Other Therapist",
            "role_names": ["THERAPIST"],
            "module_assignments": ["homecare"],
        },
    )
    assert other_user.status_code == 201, other_user.text
    approved = client.post(
        "/api/v1/integrations/v1/therapist-profiles",
        headers=headers,
        json={"user_id": other_user.json()["id"], "display_name": "Live now", "status": "APPROVED"},
    )
    assert approved.status_code == 422, approved.text
    assert "Pending" in approved.text

    duplicate = client.post(
        "/api/v1/integrations/v1/therapist-profiles",
        headers=headers,
        json={"user_id": therapist_id, "display_name": "Again"},
    )
    assert duplicate.status_code == 422, duplicate.text
    assert "already exists" in duplicate.text

    deleted = client.post(
        "/api/v1/integrations/v1/therapist-profiles",
        headers=headers,
        json={"user_id": therapist_id, "status": "DELETED"},
    )
    assert deleted.status_code == 422, deleted.text

    db = SessionLocal()
    try:
        row = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == therapist_id)).one()
        row.status = TherapistProfileStatus.DELETED
        row.deleted_at = datetime.now(timezone.utc)
        row.approved_snapshot = {"display_name": "Old listing"}
        db.commit()
        kept_id = row.id
    finally:
        db.close()

    revived = client.post(
        "/api/v1/integrations/v1/therapist-profiles",
        headers=headers,
        json={"user_id": therapist_id, "display_name": "Back online", "status": "PENDING"},
    )
    assert revived.status_code == 422, revived.text
    assert "already exists" in revived.text

    db = SessionLocal()
    try:
        row = db.get(TherapistProfile, kept_id)
        assert row is not None
        assert row.status == TherapistProfileStatus.DELETED
        assert row.deleted_at is not None
        assert row.approved_snapshot == {"display_name": "Old listing"}
    finally:
        db.close()

    if report_id is not None:
        db = SessionLocal()
        try:
            fresh = db.get(MonthlyReport, report_id)
            assert fresh.status == report_status
        finally:
            db.close()


def test_key_ttl_save_does_not_restart_or_revive(client):
    admin = login_headers(client, "superadmin@demo.com")
    created = client.post(
        "/api/v1/admin/integration-clients",
        headers=admin,
        json={
            "name": "TTL clock",
            "allow_read": True,
            "allow_write": False,
            "info_access": ["cases"],
            "access_token_minutes": 15,
            "key_ttl_days": 30,
            "mcp_enabled": False,
            "case_ids": [],
        },
    )
    assert created.status_code == 201, created.text
    client_id = created.json()["id"]

    db = SessionLocal()
    try:
        cred = db.scalars(
            select(IntegrationCredential).where(IntegrationCredential.integration_client_id == client_id)
        ).one()
        cred.created_at = datetime.now(timezone.utc) - timedelta(days=10)
        cred.expires_at = cred.created_at + timedelta(days=30)
        db.commit()
        cred_id = cred.id
        baseline = cred.expires_at
    finally:
        db.close()

    same = client.patch(
        f"/api/v1/admin/integration-clients/{client_id}",
        headers=admin,
        json={"name": "TTL clock renamed", "key_ttl_days": 30},
    )
    assert same.status_code == 200, same.text

    db = SessionLocal()
    try:
        cred = db.get(IntegrationCredential, cred_id)
        assert cred.expires_at == baseline
        created_at = cred.created_at
    finally:
        db.close()

    extended = client.patch(
        f"/api/v1/admin/integration-clients/{client_id}",
        headers=admin,
        json={"key_ttl_days": 90},
    )
    assert extended.status_code == 200, extended.text

    db = SessionLocal()
    try:
        cred = db.get(IntegrationCredential, cred_id)
        expected = created_at + timedelta(days=90)
        assert cred.expires_at == expected
        cred.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        expired_at = cred.expires_at
        db.commit()
    finally:
        db.close()

    revived = client.patch(
        f"/api/v1/admin/integration-clients/{client_id}",
        headers=admin,
        json={"key_ttl_days": 365},
    )
    assert revived.status_code == 200, revived.text

    db = SessionLocal()
    try:
        cred = db.get(IntegrationCredential, cred_id)
        stored = cred.expires_at.replace(tzinfo=None) if cred.expires_at and cred.expires_at.tzinfo else cred.expires_at
        expected = expired_at.replace(tzinfo=None) if expired_at.tzinfo else expired_at
        assert stored == expected
        assert cred.is_usable is False
    finally:
        db.close()
