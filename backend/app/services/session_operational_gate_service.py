"""Canonical case/status gates for session start (Core OS Stabilisation PR1 / DEC-02)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.timezone import today_ist
from app.models.case import Case, CaseStatus
from app.models.session import Session as TherapySession
from app.models.user import User

# Statuses that block normal new starts once effective.
_BLOCK_NORMAL_START = frozenset(
    {
        CaseStatus.CLOSED.value,
        CaseStatus.DEACTIVATED.value,
        CaseStatus.SUSPENDED.value,
        CaseStatus.PENDING_REPLACEMENT.value,
    }
)

# Prefer existing session flag for Finance review of overridden starts.
OVERRIDE_DATA_QUALITY_FLAG = "admin_start_override_finance_review"


class SessionStartBlockedError(ValueError):
    """Case/therapist operationally ineligible for a normal session start."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


def _status_value(case: Case) -> str:
    return case.status.value if hasattr(case.status, "value") else str(case.status)


def _effective_on_or_before(case: Case, as_of: date) -> bool:
    """True when status change has taken effect (null effective_date = immediate)."""
    eff = case.status_effective_date
    if eff is None:
        return True
    return as_of >= eff


def case_blocks_normal_session_start(case: Case, *, as_of: date | None = None) -> str | None:
    """
    Return a block reason code if normal starts are forbidden, else None.

    DEC-02: SUSPENDED / PENDING_REPLACEMENT / CLOSED / DEACTIVATED after effective date.
    """
    as_of = as_of or today_ist()
    current = _status_value(case)
    if current not in _BLOCK_NORMAL_START:
        return None
    if not _effective_on_or_before(case, as_of):
        # Future-dated status: still allow starts until effective day.
        return None
    if current == CaseStatus.CLOSED.value:
        return "CASE_CLOSED"
    if current == CaseStatus.DEACTIVATED.value:
        return "CASE_DEACTIVATED"
    if current == CaseStatus.SUSPENDED.value:
        return "CASE_SUSPENDED"
    if current == CaseStatus.PENDING_REPLACEMENT.value:
        return "CASE_PENDING_REPLACEMENT"
    return "CASE_NOT_OPERATIONAL"


def _block_message(code: str) -> str:
    messages = {
        "CASE_CLOSED": "Case is closed — no new sessions can be created",
        "CASE_DEACTIVATED": "Case is deactivated — no new sessions can be created",
        "CASE_SUSPENDED": (
            "This case is paused. New sessions cannot start until the case is active again "
            "(or an authorised admin override is used)."
        ),
        "CASE_PENDING_REPLACEMENT": (
            "This case is waiting for a therapist replacement. New sessions cannot start "
            "until replacement is complete (or an authorised admin override is used)."
        ),
        "CASE_NOT_OPERATIONAL": "Case is not available for new sessions right now",
        "PENDING_PAUSE_OR_CLOSE": (
            "A pause or close request is pending admin approval — you cannot start a new "
            "session until it is reviewed"
        ),
    }
    return messages.get(code, "Session cannot be started for this case right now")


def assert_case_allows_new_session(
    db: Session,
    case_id: int,
    *,
    as_of: date | None = None,
    admin_override: bool = False,
    override_reason: str | None = None,
) -> None:
    """Hard gate: case must be operationally eligible (unless authorised override)."""
    case = db.get(Case, case_id)
    if case is None:
        return

    code = case_blocks_normal_session_start(case, as_of=as_of)
    if code:
        if admin_override:
            if not (override_reason or "").strip():
                raise SessionStartBlockedError(
                    "OVERRIDE_REASON_REQUIRED",
                    "Please add a short reason so Finance can review this override start.",
                )
            return
        raise SessionStartBlockedError(code, _block_message(code))

    from app.services.case_status_request_service import get_pending_for_case

    pending = get_pending_for_case(db, case_id)
    if pending and pending.to_status in (CaseStatus.SUSPENDED.value, CaseStatus.CLOSED.value):
        if admin_override and (override_reason or "").strip():
            return
        raise SessionStartBlockedError("PENDING_PAUSE_OR_CLOSE", _block_message("PENDING_PAUSE_OR_CLOSE"))


def assert_therapist_may_operate_case(
    db: Session,
    *,
    therapist_user_id: int,
    case_id: int,
    as_of: date | None = None,
) -> None:
    """Therapist must be operationally eligible to start on this case (DEC-03)."""
    del as_of
    from app.services.therapist_eligibility_service import (
        TherapistIneligibleError,
        assert_therapist_may_hold_case,
    )

    try:
        assert_therapist_may_hold_case(db, therapist_user_id=therapist_user_id, case_id=case_id)
    except TherapistIneligibleError as exc:
        raise SessionStartBlockedError(exc.code, exc.message) from exc


def mark_session_override_for_finance_review(session: TherapySession, reason: str) -> None:
    note = (reason or "").strip()[:500]
    session.data_quality_flag = OVERRIDE_DATA_QUALITY_FLAG
    if note:
        # Preserve any existing cancellation_reason; store override text in edit reason slot if empty.
        if not getattr(session, "actual_times_edit_reason", None):
            session.actual_times_edit_reason = f"Admin start override: {note}"[:512]
