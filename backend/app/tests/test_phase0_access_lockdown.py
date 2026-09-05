"""Phase 0: CM access lockdown, multi-role resolution, MODULE_ADMIN meetings."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal
from app.core.permissions import ROLE_PERMISSIONS, RoleName, effective_role, has_role, user_role_names
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import api_first_case_id, api_items, future_meeting_date

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _headers(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_case_manager_role_permissions_stripped():
    perms = set(ROLE_PERMISSIONS[RoleName.CASE_MANAGER])
    assert "case.assign" not in perms
    assert "slot.book_any" not in perms
    assert "invoice.approve" not in perms


def test_hr_has_case_assign_not_slot_book_any():
    perms = set(ROLE_PERMISSIONS[RoleName.HR])
    assert "case.assign" in perms
    assert "slot.book_any" not in perms


def test_effective_role_precedence_ignores_insertion_order():
    class FakeRole:
        def __init__(self, name: str):
            self.name = name

    class FakeUser:
        def __init__(self, roles: list[str]):
            self.roles = [FakeRole(n) for n in roles]

        @property
        def role_names(self):
            return [r.name for r in self.roles]

    u1 = FakeUser(["CASE_MANAGER", "ADMIN"])
    u2 = FakeUser(["ADMIN", "CASE_MANAGER"])
    assert effective_role(u1) == RoleName.ADMIN.value
    assert effective_role(u2) == RoleName.ADMIN.value
    assert has_role(u1, RoleName.CASE_MANAGER)
    assert has_role(u1, RoleName.ADMIN)
    assert user_role_names(u1) == {"CASE_MANAGER", "ADMIN"}


def _therapist_user_id() -> int:
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert user is not None
        return int(user.id)


def test_cm_cannot_assign_case():
    headers = _headers("casemanager@demo.com")
    case_id = api_first_case_id(client, headers)
    therapist_id = _therapist_user_id()
    res = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=headers,
        json={"therapist_user_id": therapist_id, "start_date": date.today().isoformat()},
    )
    assert res.status_code == 403, res.text


def test_cm_cannot_book_slot_for_other_therapist():
    headers = _headers("casemanager@demo.com")
    therapist_id = _therapist_user_id()
    day = (date.today() + timedelta(days=14)).isoformat()
    res = client.post(
        "/api/v1/scheduling/slots",
        headers=headers,
        json={
            "therapist_id": therapist_id,
            "slot_date": day,
            "start_time": "10:00:00",
            "end_time": "10:30:00",
        },
    )
    assert res.status_code == 403, res.text


def test_cm_me_lacks_assign_and_slot_book_any():
    me = client.get("/api/v1/auth/me", headers=_headers("casemanager@demo.com"))
    assert me.status_code == 200
    perms = set(me.json().get("permissions") or [])
    assert "case.assign" not in perms
    assert "slot.book_any" not in perms
    assert "invoice.approve" not in perms


def test_hr_me_has_case_assign_not_slot_book_any():
    me = client.get("/api/v1/auth/me", headers=_headers("hr@demo.com"))
    assert me.status_code == 200
    perms = set(me.json().get("permissions") or [])
    assert "case.assign" in perms
    assert "slot.book_any" not in perms


def test_module_admin_can_list_and_create_meetings():
    headers = _headers("moduleadmin@demo.com")
    listed = client.get("/api/v1/meetings", headers=headers)
    assert listed.status_code == 200, listed.text

    cases = client.get("/api/v1/meetings/bookable-cases", headers=headers)
    assert cases.status_code == 200, cases.text
    bookable = cases.json()
    assert bookable, "module admin needs at least one bookable case"
    case_id = bookable[0]["id"]
    day = future_meeting_date(21)
    created = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "case_id": case_id,
            "scheduled_date": day,
            "scheduled_time": "11:00:00",
            "duration_minutes": 30,
            "meeting_type": "PARENT_MEETING",
            "invite_client": False,
            "invite_therapist": False,
        },
    )
    assert created.status_code == 201, created.text


def test_dual_role_cm_admin_behaves_as_admin_both_orders():
    """CASE_MANAGER + ADMIN must resolve to admin meetings scope regardless of role order."""
    with SessionLocal() as db:
        admin_role = db.scalars(select(Role).where(Role.name == RoleName.ADMIN.value)).first()
        cm_role = db.scalars(select(Role).where(Role.name == RoleName.CASE_MANAGER.value)).first()
        assert admin_role and cm_role

        for email, order in (
            ("dual.cmadmin.a@demo.com", [cm_role, admin_role]),
            ("dual.cmadmin.b@demo.com", [admin_role, cm_role]),
        ):
            user = db.scalars(
                select(User).options(selectinload(User.roles)).where(User.email == email)
            ).first()
            if not user:
                from app.core.security import hash_password

                user = User(
                    email=email,
                    password_hash=hash_password("demo123"),
                    full_name="Dual Role",
                    is_active=True,
                    region="south",
                    module_assignments=["homecare", "shadow_support"],
                )
                db.add(user)
                db.flush()
            user.roles = list(order)
            db.commit()
            db.refresh(user)
            assert effective_role(user) == RoleName.ADMIN.value

            headers = _headers(email)
            me = client.get("/api/v1/auth/me", headers=headers)
            assert me.status_code == 200
            perms = set(me.json().get("permissions") or [])
            assert "case.assign" in perms
            assert "slot.book_any" in perms
            listed = client.get("/api/v1/meetings", headers=headers)
            assert listed.status_code == 200, listed.text


def test_superadmin_retains_assign_and_scheduling():
    me = client.get("/api/v1/auth/me", headers=_headers("superadmin@demo.com"))
    assert me.status_code == 200
    perms = set(me.json().get("permissions") or [])
    assert "case.assign" in perms
    assert "slot.book_any" in perms
