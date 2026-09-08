"""Case Manager session log review queue — pending logs grouped by case."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.child import Child
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.user import User
from app.services import log_service
from app.services.admin_scope_service import apply_case_scope
from app.services.mentor_scope_service import is_mentor_only_on_case


def _therapist_name_for_case(db: Session, case_id: int) -> str | None:
    row = db.execute(
        select(User.full_name)
        .join(CaseAssignment, CaseAssignment.therapist_user_id == User.id)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def _session_summary(session: TherapySession, *, therapist_name: str | None = None) -> dict:
    return {
        "id": session.id,
        "status": session.status.value if hasattr(session.status, "value") else str(session.status),
        "scheduled_date": session.scheduled_date.isoformat() if session.scheduled_date else None,
        "actual_start_at": session.actual_start_at.isoformat() if session.actual_start_at else None,
        "actual_end_at": session.actual_end_at.isoformat() if session.actual_end_at else None,
        "edited_start_at": session.edited_start_at.isoformat() if getattr(session, "edited_start_at", None) else None,
        "edited_end_at": session.edited_end_at.isoformat() if getattr(session, "edited_end_at", None) else None,
        "actual_times_edited": bool(getattr(session, "actual_times_edited", False)),
        "actual_times_edit_reason": getattr(session, "actual_times_edit_reason", None),
        "duplicate_day_session": bool(getattr(session, "is_additional_visit", False)),
        "therapist_user_id": session.therapist_user_id,
        "therapist_name": therapist_name,
    }


def build_cm_log_review_queue(db: Session, user: User) -> dict:
    if not user_has_permission(user, "daily_log.review"):
        return {"total_pending": 0, "cases": []}

    stmt = (
        select(DailyLog, TherapySession, Case, Child)
        .options(selectinload(DailyLog.transition))
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .join(Case, TherapySession.case_id == Case.id)
        .join(Child, Case.child_id == Child.id)
        .where(DailyLog.approval_status == LogApprovalStatus.PENDING)
        .order_by(log_service.log_queue_order_desc())
    )
    stmt = apply_case_scope(stmt, user)
    rows = db.execute(stmt).all()

    cases_map: dict[int, dict] = {}
    all_log_dicts: list[dict] = []
    user_ids = {session.therapist_user_id for _, session, _, _ in rows}
    for log, _, _, _ in rows:
        if log.transition:
            user_ids.add(log.transition.outgoing_therapist_user_id)
            user_ids.add(log.transition.incoming_therapist_user_id)
    user_names = (
        dict(db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all())
        if user_ids
        else {}
    )

    for log, session, case, child in rows:
        log_dict = log_service.log_to_read(
            log,
            therapist_name=user_names.get(session.therapist_user_id),
        )
        status = log_dict.get("approval_status")
        if hasattr(status, "value"):
            log_dict["approval_status"] = status.value
        att = log_dict.get("attendance_status")
        if hasattr(att, "value"):
            log_dict["attendance_status"] = att.value
        log_dict["session"] = _session_summary(
            session,
            therapist_name=user_names.get(session.therapist_user_id),
        )
        all_log_dicts.append(log_dict)

        bucket = cases_map.get(case.id)
        if not bucket:
            bucket = {
                "case_id": case.id,
                "case_code": case.case_code,
                "child_name": child.full_name if child else None,
                "service_type": case.service_type,
                "product_module": case.product_module,
                "therapist_name": _therapist_name_for_case(db, case.id),
                "transition_outgoing_therapist_name": None,
                "transition_incoming_therapist_name": None,
                "status": case.status.value if hasattr(case.status, "value") else str(case.status),
                "pending_count": 0,
                "logs": [],
                "access_as_mentor": is_mentor_only_on_case(db, user, case),
                "can_approve": True,
            }
            cases_map[case.id] = bucket
        if log.transition:
            bucket["transition_outgoing_therapist_name"] = user_names.get(
                log.transition.outgoing_therapist_user_id
            )
            bucket["transition_incoming_therapist_name"] = user_names.get(
                log.transition.incoming_therapist_user_id
            )
        bucket["logs"].append(log_dict)
        bucket["pending_count"] = len(bucket["logs"])

    if all_log_dicts:
        log_service.attach_comment_counts(db, all_log_dicts, parent_visible_only=False)
        log_service.attach_mentor_review_meta(db, all_log_dicts, viewer=user)
        by_id = {d["id"]: d for d in all_log_dicts}
        for bucket in cases_map.values():
            bucket["logs"] = [by_id[lg["id"]] for lg in bucket["logs"]]

    cases = sorted(cases_map.values(), key=lambda c: (c["logs"][0].get("submitted_at") or ""), reverse=True)

    return {
        "total_pending": len(all_log_dicts),
        "cases": cases,
    }
