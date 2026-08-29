from __future__ import annotations

import io
from datetime import date, time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case_document import (
    CaseDocument,
    CaseDocumentCategory,
    CaseDocumentVisibility,
)
from app.models.case import Case
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.models.user import User
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _parent_case_id() -> int:
    res = client.get("/api/v1/parent/home", headers=_login("parent@demo.com"))
    assert res.status_code == 200, res.text
    cases = res.json().get("cases") or []
    assert cases
    return int(cases[0]["id"])


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == email)).first()
        assert user is not None
        return int(user.id)


def _create_meeting(*, case_id: int | None, scheduled_date: str, scheduled_time: str) -> dict:
    with SessionLocal() as db:
        case = db.get(Case, case_id) if case_id is not None else None
        cm_id = case.case_manager_user_id if case else _user_id("superadmin@demo.com")
        meeting = CaseManagerMeeting(
            series_id=str(uuid4()),
            case_manager_user_id=cm_id,
            case_id=case_id,
            scheduled_date=date.fromisoformat(scheduled_date),
            scheduled_time=time.fromisoformat(scheduled_time),
            duration_minutes=30,
            meeting_type=MeetingType.PARENT_MEETING,
            status=MeetingStatus.SCHEDULED,
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        return {
            "id": meeting.id,
            "series_id": meeting.series_id,
            "case_id": meeting.case_id,
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
        }


def _save_notes(meeting_id: int, *, outcome: str, summary: str, complete: bool = True, file_name: str | None = None):
    data = {
        "notes_outcome": outcome,
        "notes_summary": summary,
        "notes_next_meeting_required": "false",
        "notes_additional": "",
    }
    if complete:
        data["status"] = "COMPLETED"
    files = None
    if file_name:
        files = {"file": (file_name, io.BytesIO(b"%PDF-1.4 meeting notes"), "application/pdf")}
    return client.post(
        f"/api/v1/meetings/{meeting_id}/notes",
        headers=_login("superadmin@demo.com"),
        data=data,
        files=files,
    )


def test_meeting_document_defaults_internal_invisible_to_parent_and_assigned_therapist():
    case_id = _parent_case_id()
    meeting = _create_meeting(case_id=case_id, scheduled_date="2026-09-12", scheduled_time="10:00:00")

    res = _save_notes(
        meeting["id"],
        outcome="RESOLVED",
        summary="Shared minutes for the case team.",
        complete=True,
    )
    assert res.status_code == 200, res.text

    with SessionLocal() as db:
        doc = db.scalars(
            select(CaseDocument).where(
                CaseDocument.meeting_id == meeting["id"],
                CaseDocument.category == CaseDocumentCategory.CASE_MANAGER_MEETING_REPORT.value,
            )
        ).first()
        assert doc is not None
        assert doc.visibility == CaseDocumentVisibility.INTERNAL.value

    parent_headers = _login("parent@demo.com")
    therapist_headers = _login("therapist@demo.com")
    parent_res = client.get(f"/api/v1/documents/{doc.id}", headers=parent_headers)
    therapist_res = client.get(f"/api/v1/documents/{doc.id}", headers=therapist_headers)
    assert parent_res.status_code == 404
    assert therapist_res.status_code == 404


def test_editing_notes_updates_existing_document_not_duplicate():
    case_id = _parent_case_id()
    meeting = _create_meeting(case_id=case_id, scheduled_date="2026-09-13", scheduled_time="11:00:00")

    first = _save_notes(
        meeting["id"],
        outcome="FOLLOW_UP_REQUIRED",
        summary="Initial shared minutes.",
        complete=True,
    )
    assert first.status_code == 200, first.text

    second = _save_notes(
        meeting["id"],
        outcome="FOLLOW_UP_REQUIRED",
        summary="Updated shared minutes with one more detail.",
        complete=True,
    )
    assert second.status_code == 200, second.text

    with SessionLocal() as db:
        rows = db.scalars(
            select(CaseDocument).where(
                CaseDocument.meeting_id == meeting["id"],
                CaseDocument.category == CaseDocumentCategory.CASE_MANAGER_MEETING_REPORT.value,
            )
        ).all()
        assert len(rows) == 1


def test_non_case_meeting_cannot_attach_file():
    meeting = _create_meeting(case_id=None, scheduled_date="2026-09-14", scheduled_time="12:00:00")
    res = client.post(
        f"/api/v1/meetings/{meeting['id']}/notes",
        headers=_login("superadmin@demo.com"),
        data={
            "notes_outcome": "RESOLVED",
            "notes_summary": "Text only notes for a non-case meeting.",
            "status": "COMPLETED",
        },
        files={"file": ("minutes.pdf", io.BytesIO(b"%PDF-1.4 notes"), "application/pdf")},
    )
    assert res.status_code == 400, res.text


def test_documents_survive_reschedule_via_series_lookup():
    case_id = _parent_case_id()
    meeting = _create_meeting(case_id=case_id, scheduled_date="2026-09-15", scheduled_time="13:00:00")
    saved = _save_notes(
        meeting["id"],
        outcome="RESOLVED",
        summary="Notes before the meeting moved.",
        complete=True,
    )
    assert saved.status_code == 200, saved.text

    with SessionLocal() as db:
        old = db.get(CaseManagerMeeting, meeting["id"])
        assert old is not None
        old.status = MeetingStatus.RESCHEDULED
        old.reschedule_reason = "Family request"
        new_meeting = CaseManagerMeeting(
            series_id=old.series_id,
            case_manager_user_id=old.case_manager_user_id,
            case_id=old.case_id,
            scheduled_date=date.fromisoformat("2026-09-18"),
            scheduled_time=time.fromisoformat("15:00:00"),
            duration_minutes=30,
            meeting_type=old.meeting_type,
            status=MeetingStatus.SCHEDULED,
            rescheduled_from_id=old.id,
        )
        db.add(new_meeting)
        db.commit()
        db.refresh(new_meeting)
        new_meeting = {
            "id": new_meeting.id,
            "series_id": new_meeting.series_id,
        }

    docs_res = client.get(f"/api/v1/meetings/{new_meeting['id']}/documents", headers=_login("superadmin@demo.com"))
    assert docs_res.status_code == 200, docs_res.text
    docs = docs_res.json()
    assert docs
    meeting_doc = next(item for item in docs if item["category"] == CaseDocumentCategory.CASE_MANAGER_MEETING_REPORT.value)
    assert meeting_doc["meeting_series_id"] == new_meeting["series_id"]
    assert meeting_doc["meeting_scheduled_date"] == "2026-09-18"
