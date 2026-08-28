"""Parent portal auto-suspend / auto-reactivate when cases close or reopen."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select

from app.core.audit import log_audit
from app.core.database import SessionLocal
from app.core.permissions import RoleName
from app.core.security import hash_password
from app.models.audit_event import AuditEvent
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.parent import ParentGuardian, parent_child_link
from app.models.role import Role
from app.models.user import User
from app.services import client_status_service


def _admin(db) -> User:
    user = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
    assert user is not None
    return user


def _make_parent_with_cases(db, *, case_count: int = 1) -> tuple[User, list[Case]]:
    suffix = uuid.uuid4().hex[:8]
    role = db.scalars(select(Role).where(Role.name == RoleName.PARENT.value)).first()
    assert role is not None

    parent = User(
        email=f"auto-suspend-parent-{suffix}@demo.com",
        password_hash=hash_password("demo123"),
        full_name=f"Auto Suspend Parent {suffix}",
        is_active=True,
    )
    parent.roles = [role]
    db.add(parent)
    db.flush()

    pg = ParentGuardian(user_id=parent.id)
    db.add(pg)
    db.flush()

    child = Child(first_name="Auto", last_name=suffix)
    db.add(child)
    db.flush()
    db.execute(
        parent_child_link.insert().values(parent_guardian_id=pg.id, child_id=child.id)
    )

    cm = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
    cases: list[Case] = []
    for i in range(case_count):
        case = Case(
            case_code=f"IC-AS-{suffix}-{i}",
            child_id=child.id,
            service_type="Homecare",
            product_module="homecare",
            status=CaseStatus.ACTIVE,
            case_manager_user_id=cm.id if cm else None,
        )
        db.add(case)
        cases.append(case)
    db.flush()
    return parent, cases


def _close_case(db, case: Case, actor: User) -> None:
    client_status_service.change_client_status(
        db,
        case,
        actor,
        CaseStatus.CLOSED.value,
        effective_date=date.today(),
        reason="Closing for parent portal auto-suspend test",
    )


def _reopen_case(db, case: Case, actor: User) -> None:
    client_status_service.change_client_status(
        db,
        case,
        actor,
        CaseStatus.PENDING_ALLOTMENT.value,
        effective_date=date.today(),
        reason="Reopening for parent portal auto-reactivate test",
    )


def _latest_actions(db, parent_id: int) -> list[str]:
    rows = db.scalars(
        select(AuditEvent.action)
        .where(
            AuditEvent.entity_type == "user",
            AuditEvent.entity_id == str(parent_id),
            AuditEvent.action.in_(
                (
                    "parent_portal_auto_suspend",
                    "parent_portal_auto_reactivate",
                    "deactivate",
                )
            ),
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    ).all()
    return list(rows)


def test_closing_only_case_auto_suspends_parent():
    db = SessionLocal()
    try:
        actor = _admin(db)
        parent, cases = _make_parent_with_cases(db, case_count=1)
        assert parent.is_active is True

        _close_case(db, cases[0], actor)
        db.commit()

        db.refresh(parent)
        assert parent.is_active is False
        assert _latest_actions(db, parent.id)[0] == "parent_portal_auto_suspend"
    finally:
        db.close()


def test_closing_one_of_two_cases_does_not_suspend_parent():
    db = SessionLocal()
    try:
        actor = _admin(db)
        parent, cases = _make_parent_with_cases(db, case_count=2)
        assert len(cases) == 2
        assert parent.is_active is True

        _close_case(db, cases[0], actor)
        db.commit()

        db.refresh(parent)
        assert parent.is_active is True
        assert "parent_portal_auto_suspend" not in _latest_actions(db, parent.id)
    finally:
        db.close()


def test_reopening_auto_reactivates_auto_suspended_parent():
    db = SessionLocal()
    try:
        actor = _admin(db)
        parent, cases = _make_parent_with_cases(db, case_count=1)

        _close_case(db, cases[0], actor)
        db.commit()
        db.refresh(parent)
        assert parent.is_active is False

        _reopen_case(db, cases[0], actor)
        db.commit()
        db.refresh(parent)
        assert parent.is_active is True
        actions = _latest_actions(db, parent.id)
        assert actions[0] == "parent_portal_auto_reactivate"
        assert "parent_portal_auto_suspend" in actions
    finally:
        db.close()


def test_manually_suspended_parent_is_not_auto_reactivated():
    db = SessionLocal()
    try:
        actor = _admin(db)
        parent, cases = _make_parent_with_cases(db, case_count=1)

        # Manual deactivate without auto-suspend audit (set is_active=False + deactivate audit).
        parent.is_active = False
        log_audit(
            db,
            actor_user_id=actor.id,
            action="deactivate",
            entity_type="user",
            entity_id=parent.id,
            new_value={"is_active": False, "cause": "manual_test"},
        )
        # Close the case so reopen path runs; parent was never auto-suspended.
        _close_case(db, cases[0], actor)
        db.commit()
        db.refresh(parent)
        assert parent.is_active is False

        _reopen_case(db, cases[0], actor)
        db.commit()
        db.refresh(parent)
        assert parent.is_active is False
        assert "parent_portal_auto_reactivate" not in _latest_actions(db, parent.id)
    finally:
        db.close()
