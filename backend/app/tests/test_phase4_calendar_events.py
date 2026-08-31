from __future__ import annotations

from datetime import date, datetime, timedelta, time

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models import Case, Child, ParentGuardian, TherapySession, User
from app.models.case import CaseStatus
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.models.session import SessionStatus
from app.services import availability_service
from app.tests.conftest import login_headers

client = TestClient(app)


def _make_child_case(db, *, child_name: str, case_code: str, case_manager_user_id: int) -> Case:
    child = Child(first_name=child_name, last_name="Demo")
    db.add(child)
    db.flush()
    case = Case(
        case_code=case_code,
        child_id=child.id,
        service_type="Homecare",
        product_module="homecare",
        status=CaseStatus.ACTIVE,
        case_manager_user_id=case_manager_user_id,
        region="south",
    )
    db.add(case)
    db.flush()
    return case


def test_therapist_with_session_and_meeting_sees_both():
    headers = login_headers(client, "therapist@demo.com")
    target = date.today() + timedelta(days=21)

    with SessionLocal() as db:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case_manager = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
        assert therapist is not None
        assert case_manager is not None

        case = _make_child_case(db, child_name="Unified", case_code="IC-UNIFIED-001", case_manager_user_id=case_manager.id)
        db.add(
            TherapySession(
                case_id=case.id,
                therapist_user_id=therapist.id,
                scheduled_date=target,
                start_time=time(9, 0),
                end_time=time(10, 0),
                status=SessionStatus.SCHEDULED,
            )
        )
        db.add(
            CaseManagerMeeting(
                case_manager_user_id=case_manager.id,
                case_id=case.id,
                therapist_user_id=therapist.id,
                scheduled_date=target,
                scheduled_time=time(11, 0),
                duration_minutes=30,
                meeting_type=MeetingType.PARENT_MEETING,
                title="Team sync",
                status=MeetingStatus.SCHEDULED,
            )
        )
        db.commit()

    res = client.get(
        "/api/v1/calendar/events",
        headers=headers,
        params={"from": target.isoformat(), "to": target.isoformat()},
    )
    assert res.status_code == 200, res.text
    events = res.json()["events"]
    kinds = {event["event_type"] for event in events}
    assert "therapy_session" in kinds
    assert "cm_meeting" in kinds
    assert all(event["date"] == target.isoformat() for event in events)


def test_parent_sees_only_own_child_meetings():
    headers = login_headers(client, "parent@demo.com")
    target = date.today() + timedelta(days=22)
    parent_case_id = None
    other_case_id = None

    with SessionLocal() as db:
        parent = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        case_manager = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert parent is not None
        assert case_manager is not None
        assert therapist is not None

        parent_child = Child(first_name="Parent", last_name="Own")
        db.add(parent_child)
        db.flush()
        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == parent.id)).first()
        if pg is None:
            pg = ParentGuardian(user_id=parent.id)
            db.add(pg)
            db.flush()
        if parent_child not in pg.children:
            pg.children.append(parent_child)

        parent_case = Case(
            case_code="IC-PARENT-001",
            child_id=parent_child.id,
            service_type="Homecare",
            product_module="homecare",
            status=CaseStatus.ACTIVE,
            case_manager_user_id=case_manager.id,
            region="south",
        )
        db.add(parent_case)
        db.flush()

        other_case = _make_child_case(db, child_name="Other", case_code="IC-PARENT-002", case_manager_user_id=case_manager.id)

        db.add(
            CaseManagerMeeting(
                case_manager_user_id=case_manager.id,
                case_id=parent_case.id,
                parent_user_id=parent.id,
                therapist_user_id=therapist.id,
                scheduled_date=target,
                scheduled_time=time(10, 0),
                duration_minutes=30,
                meeting_type=MeetingType.PARENT_MEETING,
                title="Own child meeting",
                status=MeetingStatus.SCHEDULED,
            )
        )
        db.add(
            CaseManagerMeeting(
                case_manager_user_id=case_manager.id,
                case_id=other_case.id,
                therapist_user_id=therapist.id,
                scheduled_date=target,
                scheduled_time=time(11, 0),
                duration_minutes=30,
                meeting_type=MeetingType.PARENT_MEETING,
                title="Other child meeting",
                status=MeetingStatus.SCHEDULED,
            )
        )
        db.commit()
        parent_case_id = parent_case.id
        other_case_id = other_case.id

    res = client.get(
        "/api/v1/calendar/events",
        headers=headers,
        params={"from": target.isoformat(), "to": target.isoformat()},
    )
    assert res.status_code == 200, res.text
    events = res.json()["events"]
    cm_events = [e for e in events if e.get("event_type") == "cm_meeting"]
    assert cm_events
    assert all(e.get("case_id") != other_case_id for e in cm_events)
    assert any(e.get("case_id") == parent_case_id for e in cm_events)


def test_external_busy_has_no_title(monkeypatch):
    headers = login_headers(client, "therapist@demo.com")
    target = date.today() + timedelta(days=23)

    with SessionLocal() as db:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist is not None

    busy_start = datetime.combine(target, time(14, 0), tzinfo=availability_service.IST)
    busy_end = datetime.combine(target, time(15, 0), tzinfo=availability_service.IST)

    monkeypatch.setattr(
        availability_service,
        "external_busy_intervals",
        lambda _db, user_ids, date_from, date_to: {therapist.id: [(busy_start, busy_end)]},
    )

    res = client.get(
        "/api/v1/calendar/events",
        headers=headers,
        params={"from": target.isoformat(), "to": target.isoformat()},
    )
    assert res.status_code == 200, res.text
    events = res.json()["events"]
    assert len(events) == 1
    assert events[0]["event_type"] == "external_busy"
    assert events[0]["title"] is None
    assert events[0]["date"] == target.isoformat()

