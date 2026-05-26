from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import SessionLocal
from app.core.permissions import RoleName
from app.seed.demo_seed import get_or_create_user, seed_roles_permissions
from app.main import app
from app.models.case import Case
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services.admin_home_service import PRIMARY_ROLE_PRIORITY, resolve_primary_role
from app.services.admin_scope_service import apply_case_scope, user_sees_global_cases

client = TestClient(app)

HIDDEN_WORKBENCH_KEYS = frozenset(
    {"incidents", "iep", "meetings", "workbench", "sections"}
)
FORBIDDEN_HOME_WIDGETS_BY_ROLE: dict[str, frozenset[str]] = {
    "FINANCE": frozenset({"logs", "reports", "reschedules"}),
    "HR": frozenset({"logs", "reports", "billing", "reschedules"}),
}
EXPECTED_WIDGETS_BY_ROLE: dict[str, frozenset[str]] = {
    "SUPER_ADMIN": frozenset(
        {"logs", "reports", "billing", "tickets", "reschedules", "observations", "status_requests", "client_claims"}
    ),
    "MODULE_ADMIN": frozenset(
        {"logs", "reports", "billing", "tickets", "reschedules", "observations", "status_requests", "client_claims"}
    ),
    "CASE_MANAGER": frozenset({"logs", "reports", "tickets", "reschedules", "observations", "status_requests"}),
    "FINANCE": frozenset({"billing", "client_claims"}),
    "HR": frozenset({"tickets"}),
}


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _home(email: str) -> dict:
    r = client.get("/api/v1/admin/home", headers=_login(email))
    assert r.status_code == 200, r.text
    return r.json()


def _widget_case_ids(home: dict) -> set[int]:
    ids: set[int] = set()
    for widget in home.get("widgets", []):
        for item in widget.get("section", {}).get("items") or []:
            cid = item.get("case_id")
            if cid is not None:
                ids.add(int(cid))
    return ids


def _assert_no_hidden_workbench_payload(home: dict) -> None:
    assert "workbench" not in home
    for key in HIDDEN_WORKBENCH_KEYS:
        assert key not in home, f"unexpected top-level key {key}"
    for widget in home.get("widgets", []):
        section = widget.get("section") or {}
        for key in ("incidents", "iep", "meetings"):
            assert key not in section


@pytest.mark.parametrize(
    "email,expected_role,landing_route",
    [
        ("superadmin@demo.com", "SUPER_ADMIN", "/admin"),
        ("admin@demo.com", "MODULE_ADMIN", "/admin"),
        ("moduleadmin@demo.com", "MODULE_ADMIN", "/admin"),
        ("casemanager@demo.com", "CASE_MANAGER", "/admin/cm"),
        ("shadowcm@demo.com", "CASE_MANAGER", "/admin/cm"),
        ("viewonly@demo.com", "CASE_MANAGER", "/admin/cm"),
        ("finance@demo.com", "FINANCE", "/admin/invoices"),
        ("hr@demo.com", "HR", "/admin/people"),
    ],
)
def test_admin_home_role_label_and_landing(email, expected_role, landing_route):
    home = _home(email)
    assert home["role"] == expected_role
    assert home["landing_route"] == landing_route
    _assert_no_hidden_workbench_payload(home)


@pytest.mark.parametrize(
    "email,expected_role,expected_widgets",
    [
        ("superadmin@demo.com", "SUPER_ADMIN", "SUPER_ADMIN"),
        ("admin@demo.com", "MODULE_ADMIN", "MODULE_ADMIN_HOME_ONLY"),
        ("moduleadmin@demo.com", "MODULE_ADMIN", "MODULE_ADMIN"),
        ("casemanager@demo.com", "CASE_MANAGER", "CASE_MANAGER"),
        ("shadowcm@demo.com", "CASE_MANAGER", "CASE_MANAGER"),
        ("viewonly@demo.com", "CASE_MANAGER", "CASE_MANAGER"),
        ("finance@demo.com", "FINANCE", "FINANCE"),
        ("hr@demo.com", "HR", "HR"),
    ],
)
def test_admin_home_widget_ids_match_role(email, expected_role, expected_widgets):
    home = _home(email)
    assert home["role"] == expected_role
    widget_ids = {w["id"] for w in home["widgets"]}
    key = expected_widgets
    if key == "MODULE_ADMIN_HOME_ONLY":
        expected = frozenset(
            {"logs", "reports", "tickets", "reschedules", "observations", "status_requests"}
        )
    else:
        expected = EXPECTED_WIDGETS_BY_ROLE[key]
    assert expected <= widget_ids, f"missing widgets {expected - widget_ids}"
    forbidden = FORBIDDEN_HOME_WIDGETS_BY_ROLE.get(expected_role, frozenset())
    assert not widget_ids.intersection(forbidden)


def test_admin_home_includes_alerts_list():
    home = _home("casemanager@demo.com")
    assert "alerts" in home
    assert isinstance(home["alerts"], list)


def test_workbench_summary_includes_ops_sections():
    headers = _login("casemanager@demo.com")
    r = client.get("/api/v1/admin/workbench/summary", headers=headers)
    assert r.status_code == 200
    sections = r.json().get("sections") or {}
    assert "observations" in sections or "status_requests" in sections or "reports" in sections


def test_dashboard_summary_includes_ops_counts():
    headers = _login("superadmin@demo.com")
    r = client.get("/api/v1/admin/dashboard/summary", headers=headers)
    assert r.status_code == 200
    data = r.json()
    for key in (
        "observation_checklists_pending",
        "status_requests_pending",
        "client_payments_pending_review",
        "iep_attention",
        "iep_plans_draft",
    ):
        assert key in data


def test_finance_billing_widget_uses_invoice_features():
    home = _home("finance@demo.com")
    billing = next(w for w in home["widgets"] if w["id"] == "billing")
    assert billing["section"] is not None
    assert "count" in billing["section"]
    assert "items" in billing["section"]


def test_reschedules_widget_id_and_pending_label():
    home = _home("casemanager@demo.com")
    widget = next(w for w in home["widgets"] if w["id"] == "reschedules")
    assert widget["title"] == "Pending reschedules"
    for item in widget.get("section", {}).get("items") or []:
        assert item.get("status") == "PENDING_THERAPIST" or "Reschedule pending" in (
            item.get("label") or ""
        )


def test_case_manager_widget_cases_subset_of_superadmin():
    sa_home = _home("superadmin@demo.com")
    cm_home = _home("casemanager@demo.com")
    sa_ids = _widget_case_ids(sa_home)
    cm_ids = _widget_case_ids(cm_home)
    if cm_ids and sa_ids:
        assert cm_ids <= sa_ids


def test_case_manager_and_supervisor_widget_cases_pass_team_scope():
    db = SessionLocal()
    try:
        for email in ("casemanager@demo.com", "shadowcm@demo.com"):
            user = db.scalars(
                select(User).where(User.email == email).options(selectinload(User.roles))
            ).first()
            assert user is not None
            assert not user_sees_global_cases(user)
            home = _home(email)
            scoped_stmt = apply_case_scope(select(Case.id), user)
            allowed_ids = set(db.scalars(scoped_stmt).all())
            for case_id in _widget_case_ids(home):
                assert case_id in allowed_ids, f"{email} case {case_id} outside team scope"
    finally:
        db.close()


def test_school_coordinator_gets_403_on_admin_home():
    db = SessionLocal()
    try:
        seed_roles_permissions(db)
        user = db.scalars(select(User).where(User.email == "schoolcoord@demo.com")).first()
        if not user:
            user = get_or_create_user(
                db,
                "schoolcoord@demo.com",
                "demo123",
                "School Coordinator",
                RoleName.SCHOOL_COORDINATOR.value,
                module_assignments=["shadow_support"],
            )
            db.commit()
    finally:
        db.close()

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "schoolcoord@demo.com", "password": "demo123"},
    )
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    home = client.get("/api/v1/admin/home", headers=headers)
    assert home.status_code == 403


def test_primary_role_priority_order_documented():
    assert PRIMARY_ROLE_PRIORITY[0] == RoleName.SUPER_ADMIN
    assert RoleName.MODULE_ADMIN in PRIMARY_ROLE_PRIORITY
    assert PRIMARY_ROLE_PRIORITY.index(RoleName.MODULE_ADMIN) < PRIMARY_ROLE_PRIORITY.index(RoleName.ADMIN)
    assert RoleName.SUPERVISOR in PRIMARY_ROLE_PRIORITY
    assert PRIMARY_ROLE_PRIORITY.index(RoleName.SUPERVISOR) < PRIMARY_ROLE_PRIORITY.index(
        RoleName.CASE_MANAGER
    )


def test_migrated_supervisor_demo_is_case_manager():
    db = SessionLocal()
    try:
        user = db.scalars(
            select(User).where(User.email == "shadowcm@demo.com").options(selectinload(User.roles))
        ).first()
        assert resolve_primary_role(user) == "CASE_MANAGER"
    finally:
        db.close()


def test_admin_home_includes_dashboard_variant():
    home = _home("finance@demo.com")
    assert home.get("dashboard_variant") == "finance"
    assert _home("moduleadmin@demo.com").get("dashboard_variant") == "module_admin"


# TODO(product): If SCHOOL_COORDINATOR is enabled on /admin/home, scope widgets to
# school-specific cases — not module-wide case.read.scoped.
