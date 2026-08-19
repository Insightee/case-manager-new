"""Due therapist-transition auto-complete must not 500 case load or report start."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.case_therapist_transition import CaseTherapistTransitionStatus
from app.services import therapist_transition_service

client = TestClient(app)
ensure_sqlite_schema_patches()


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows
        self.flushed = False

    def scalars(self, _query):
        return _FakeScalars(self._rows)

    def flush(self):
        self.flushed = True

    @contextmanager
    def begin_nested(self):
        yield


class _Row:
    def __init__(self, row_id: int, raw_dates):
        self.id = row_id
        self.status = CaseTherapistTransitionStatus.SCHEDULED
        self.transition_dates = raw_dates


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_complete_due_transitions_ignores_empty_and_bad_dates():
    db = _FakeDB(
        [
            _Row(1, None),
            _Row(2, []),
            _Row(3, ["not-a-date", None]),
        ]
    )
    assert therapist_transition_service.complete_due_transitions(db) == []


def test_complete_due_transitions_billing_failure_does_not_raise(monkeypatch):
    overdue = [(date.today() - timedelta(days=5 + i)).isoformat() for i in range(3)]
    db = _FakeDB([_Row(9, overdue)])

    def boom(*_args, **_kwargs):
        raise ValueError("The billing approver is not available. Please contact an administrator.")

    monkeypatch.setattr(therapist_transition_service, "complete_transition", boom)
    assert therapist_transition_service.complete_due_transitions(db) == []


def test_complete_due_transition_for_case_ignores_empty_dates(monkeypatch):
    row = _Row(4, None)
    monkeypatch.setattr(therapist_transition_service, "active_transition_for_case", lambda *_a, **_k: row)
    result = therapist_transition_service.complete_due_transition_for_case(_FakeDB([]), case_id=1)
    assert result is row


def test_list_assignments_ok_when_due_complete_raises(monkeypatch):
    def boom(_db, **_kwargs):
        raise RuntimeError("billing approver missing")

    monkeypatch.setattr(
        "app.services.therapist_transition_service.complete_due_transitions",
        boom,
    )
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        case_id = case.id

    r = client.get(f"/api/v1/cases/{case_id}/assignments", headers=headers)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
