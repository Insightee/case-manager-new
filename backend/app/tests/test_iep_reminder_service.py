"""IEP deadline reminder constants."""

from __future__ import annotations

from app.services import iep_reminder_service as svc


def test_reminder_kind_labels():
    assert svc.REMINDER_KINDS[25][0] == "iep_start_draft"
    assert svc.REMINDER_KINDS[35][0] == "iep_due_soon"
    assert svc.REMINDER_KINDS[45][0] == "iep_deadline"
    assert svc.REMINDER_KINDS[5][0] == "iep_renewal_start"
    assert svc.REMINDER_KINDS[20][0] == "iep_renewal_deadline"


def test_window_constants():
    assert svc.INITIAL_WINDOW_DAYS == 45
    assert svc.RENEWAL_WINDOW_DAYS == 20
