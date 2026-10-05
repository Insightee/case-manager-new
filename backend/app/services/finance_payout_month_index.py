"""Load one billing month so payout preview does not query once per case."""
from __future__ import annotations

from collections import defaultdict
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case_therapist_transition import CaseTherapistTransitionDay
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.therapist_profile import TherapistProfile

_NOT_DELIVERED = (
    SessionStatus.CANCELLED,
    SessionStatus.RESCHEDULED,
    SessionStatus.NO_SHOW,
)
_APPROVED = LogApprovalStatus.APPROVED.value
_PENDING = LogApprovalStatus.PENDING.value


@dataclass
class _SessionFact:
    id: int
    case_id: int
    therapist_user_id: int
    status: SessionStatus
    scheduled_date: date
    actual_start_at: datetime | None
    actual_end_at: datetime | None
    start_time: time | None
    end_time: time | None
    logs: list[tuple[str | None, int | None]] = field(default_factory=list)


@dataclass
class MonthIndex:
    start: date
    end: date
    sessions_by_pair: dict[tuple[int, int], list[_SessionFact]]
    assignments_by_case: dict[int, list[CaseAssignment]]
    employment_start: dict[int, date | None]
    first_session: dict[tuple[int, int], date]
    first_approved: dict[tuple[int, int], date]
    last_approved: dict[tuple[int, int], date]
    absences: list[tuple]
    transitions: dict[tuple[int, int], list[tuple]]

    def _sessions(self, case_id: int, therapist_user_id: int) -> list[_SessionFact]:
        return self.sessions_by_pair.get((case_id, therapist_user_id), [])

    def approved_sessions(self, case_id: int, therapist_user_id: int) -> int:
        count = 0
        for session in self._sessions(case_id, therapist_user_id):
            if session.status != SessionStatus.COMPLETED:
                continue
            count += sum(1 for approval, transition_id in session.logs if approval == _APPROVED and transition_id is None)
        return count

    def logged_sessions(self, case_id: int, therapist_user_id: int) -> int:
        return sum(
            1
            for session in self._sessions(case_id, therapist_user_id)
            if session.actual_start_at is not None
            and session.actual_end_at is not None
            and session.status not in _NOT_DELIVERED
        )

    def payable_sessions(self, case_id: int, therapist_user_id: int) -> int:
        ids: set[int] = set()
        for session in self._sessions(case_id, therapist_user_id):
            clocked = (
                session.actual_start_at is not None
                and session.actual_end_at is not None
                and session.status not in _NOT_DELIVERED
            )
            approved = session.status == SessionStatus.COMPLETED and any(
                approval == _APPROVED and transition_id is None for approval, transition_id in session.logs
            )
            if clocked or approved:
                ids.add(session.id)
        return len(ids)

    def child_absence(self, case_id: int, therapist_user_id: int) -> int:
        return sum(
            1
            for session in self._sessions(case_id, therapist_user_id)
            if session.status == SessionStatus.CLIENT_ABSENT
        )

    def pending_sessions(self, case_id: int, therapist_user_id: int) -> int:
        count = 0
        for session in self._sessions(case_id, therapist_user_id):
            if session.status != SessionStatus.COMPLETED:
                continue
            count += sum(1 for approval, _transition in session.logs if approval == _PENDING)
        return count

    def pending_absence(self, case_id: int, therapist_user_id: int) -> int:
        return sum(
            1
            for row_case, row_therapist, _session_status, absence_type, absence_status in self.absences
            if row_case == case_id
            and row_therapist == therapist_user_id
            and absence_type == SessionAbsenceType.CLIENT_ABSENT
            and absence_status == SessionAbsenceStatus.PENDING_APPROVAL
        )

    def approved_absence(self, case_id: int, therapist_user_id: int) -> int:
        return sum(
            1
            for row_case, row_therapist, session_status, absence_type, absence_status in self.absences
            if row_case == case_id
            and row_therapist == therapist_user_id
            and session_status == SessionStatus.CLIENT_ABSENT
            and absence_type == SessionAbsenceType.CLIENT_ABSENT
            and absence_status == SessionAbsenceStatus.APPROVED
        )

    def hours(self, case_id: int, therapist_user_id: int) -> float:
        total = 0.0
        for session in self._sessions(case_id, therapist_user_id):
            if session.status != SessionStatus.COMPLETED:
                continue
            minutes = 0
            if session.actual_start_at and session.actual_end_at:
                minutes = int((session.actual_end_at - session.actual_start_at).total_seconds() / 60)
            elif session.start_time and session.end_time:
                start_dt = datetime.combine(session.scheduled_date, session.start_time)
                end_dt = datetime.combine(session.scheduled_date, session.end_time)
                minutes = int((end_dt - start_dt).total_seconds() / 60)
            total += minutes / 60.0
        return total

    def assignment_for_month(self, case_id: int, therapist_user_id: int) -> CaseAssignment | None:
        matches = [
            row
            for row in self.assignments_by_case.get(case_id, [])
            if int(row.therapist_user_id) == therapist_user_id
            and row.start_date <= self.end
            and (row.end_date is None or row.end_date >= self.start)
        ]
        if not matches:
            return None
        return max(matches, key=lambda row: row.start_date)

    def assignment_start(
        self, case_id: int, therapist_user_id: int, reference_date: date | None
    ) -> date | None:
        current = self.assignment_for_month(case_id, therapist_user_id)
        if current is not None:
            return current.start_date
        rows = [
            row
            for row in self.assignments_by_case.get(case_id, [])
            if int(row.therapist_user_id) == therapist_user_id
        ]
        if reference_date is not None:
            prior = [row for row in rows if row.start_date <= reference_date]
            if prior:
                return max(prior, key=lambda row: row.start_date).start_date
        if not rows:
            return None
        return max(rows, key=lambda row: row.start_date).start_date

    def is_incoming(self, case_id: int, therapist_user_id: int) -> bool:
        assignment = self.assignment_for_month(case_id, therapist_user_id)
        if assignment is None:
            return False
        return any(
            int(row.therapist_user_id) != therapist_user_id and row.start_date < assignment.start_date
            for row in self.assignments_by_case.get(case_id, [])
        )

    def is_outgoing(self, case_id: int, therapist_user_id: int) -> bool:
        assignment = self.assignment_for_month(case_id, therapist_user_id)
        if assignment is None:
            return False
        if assignment.status in (CaseAssignmentStatus.TRANSFERRED, CaseAssignmentStatus.ENDED):
            return True
        return any(
            int(row.therapist_user_id) != therapist_user_id and row.start_date > assignment.start_date
            for row in self.assignments_by_case.get(case_id, [])
        )

    def overlapping_assignments(self, case_id: int) -> list[CaseAssignment]:
        return [
            row
            for row in self.assignments_by_case.get(case_id, [])
            if row.start_date <= self.end and (row.end_date is None or row.end_date >= self.start)
        ]
        return sorted(matches, key=lambda row: row.id or 0, reverse=True)

    def transition_pay(self, case_id: int, therapist_user_id: int) -> tuple[int, str, float]:
        rows = self.transitions.get((case_id, therapist_user_id), [])
        unique_days = {int(day_id): (day_type, rate) for day_id, day_type, rate in rows}
        day_types = {str(day_type or "FULL_DAY") for day_type, _rate in unique_days.values()}
        labels = {"HALF_DAY": "Half day", "FULL_DAY": "Full day"}
        day_type_label = ", ".join(
            sorted(labels.get(value, value.replace("_", " ").title()) for value in day_types)
        )
        total = round(sum(float(rate or 0) for _day_type, rate in unique_days.values()), 2)
        return len(unique_days), day_type_label, total


_current: ContextVar[MonthIndex | None] = ContextVar("finance_payout_month_index", default=None)


def current() -> MonthIndex | None:
    return _current.get()


def active(start: date, end: date) -> MonthIndex | None:
    index = _current.get()
    if index is None or index.start != start or index.end != end:
        return None
    return index


def load_month_index(db: Session, *, start: date, end: date, case_ids: list[int]) -> MonthIndex:
    session_rows = db.execute(
        select(
            TherapySession.id,
            TherapySession.case_id,
            TherapySession.therapist_user_id,
            TherapySession.status,
            TherapySession.scheduled_date,
            TherapySession.actual_start_at,
            TherapySession.actual_end_at,
            TherapySession.start_time,
            TherapySession.end_time,
        ).where(
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
        )
    ).all()
    facts = {
        int(row.id): _SessionFact(
            id=int(row.id),
            case_id=int(row.case_id),
            therapist_user_id=int(row.therapist_user_id),
            status=row.status,
            scheduled_date=row.scheduled_date,
            actual_start_at=row.actual_start_at,
            actual_end_at=row.actual_end_at,
            start_time=row.start_time,
            end_time=row.end_time,
        )
        for row in session_rows
    }
    if facts:
        log_rows = db.execute(
            select(DailyLog.session_id, DailyLog.approval_status, DailyLog.transition_id).where(
                DailyLog.session_id.in_(list(facts))
            )
        ).all()
        for session_id, approval, transition_id in log_rows:
            fact = facts.get(int(session_id))
            if fact is not None:
                approval_value = approval.value if hasattr(approval, "value") else approval
                fact.logs.append((approval_value, transition_id))

    by_pair: dict[tuple[int, int], list[_SessionFact]] = defaultdict(list)
    for fact in facts.values():
        by_pair[(fact.case_id, fact.therapist_user_id)].append(fact)

    assignments: dict[int, list[CaseAssignment]] = defaultdict(list)
    if case_ids:
        for row in db.scalars(select(CaseAssignment).where(CaseAssignment.case_id.in_(case_ids))).all():
            assignments[int(row.case_id)].append(row)

    employment = {
        int(user_id): started
        for user_id, started in db.execute(
            select(TherapistProfile.user_id, TherapistProfile.employment_start_date)
        ).all()
    }
    first_session = {
        (int(case_id), int(therapist_id)): started
        for case_id, therapist_id, started in db.execute(
            select(
                TherapySession.case_id,
                TherapySession.therapist_user_id,
                func.min(TherapySession.scheduled_date),
            ).group_by(TherapySession.case_id, TherapySession.therapist_user_id)
        ).all()
        if started is not None
    }
    approved_bounds = db.execute(
        select(
            TherapySession.case_id,
            TherapySession.therapist_user_id,
            func.min(TherapySession.scheduled_date),
            func.max(TherapySession.scheduled_date),
        )
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            DailyLog.approval_status == _APPROVED,
            DailyLog.transition_id.is_(None),
        )
        .group_by(TherapySession.case_id, TherapySession.therapist_user_id)
    ).all()
    first_approved = {
        (int(case_id), int(therapist_id)): first
        for case_id, therapist_id, first, _last in approved_bounds
        if first is not None
    }
    last_approved = {
        (int(case_id), int(therapist_id)): last
        for case_id, therapist_id, _first, last in approved_bounds
        if last is not None
    }
    absences = db.execute(
        select(
            TherapySession.case_id,
            TherapySession.therapist_user_id,
            TherapySession.status,
            SessionAbsenceRequest.absence_type,
            SessionAbsenceRequest.status,
        )
        .join(TherapySession, TherapySession.id == SessionAbsenceRequest.session_id)
        .where(
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
        )
    ).all()
    transition_rows = db.execute(
        select(
            TherapySession.case_id,
            TherapySession.therapist_user_id,
            CaseTherapistTransitionDay.id,
            CaseTherapistTransitionDay.day_type,
            CaseTherapistTransitionDay.pay_rate_inr,
        )
        .join(DailyLog, DailyLog.transition_day_id == CaseTherapistTransitionDay.id)
        .join(TherapySession, TherapySession.id == DailyLog.session_id)
        .where(
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
            DailyLog.approval_status == _APPROVED,
        )
    ).all()
    transitions: dict[tuple[int, int], list[tuple]] = defaultdict(list)
    for case_id, therapist_id, day_id, day_type, rate in transition_rows:
        transitions[(int(case_id), int(therapist_id))].append((day_id, day_type, rate))

    return MonthIndex(
        start=start,
        end=end,
        sessions_by_pair=dict(by_pair),
        assignments_by_case=dict(assignments),
        employment_start=employment,
        first_session=first_session,
        first_approved=first_approved,
        last_approved=last_approved,
        absences=list(absences),
        transitions=dict(transitions),
    )


def activate(index: MonthIndex) -> Token:
    return _current.set(index)


def reset(token: Token) -> None:
    _current.reset(token)
