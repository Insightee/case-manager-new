"""IEP stakeholder approval — parent/therapist sign-off with 10-day auto-approve."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_report import ClinicalReport, ClinicalReportReviewEvent, ClinicalReportStatus
from app.models.user import User
from app.services import report_status_service

AUTO_APPROVE_DAYS = 10
STAKEHOLDER_STATUSES = frozenset({"pending", "approved", "auto_approved", "review_requested"})


def _json_loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _json_dumps(data: dict) -> str:
    return json.dumps(data)


def _meta(report: ClinicalReport) -> dict:
    return _json_loads(report.metadata_json)


def _save_meta(db: Session, report: ClinicalReport, meta: dict) -> None:
    report.metadata_json = _json_dumps(meta)
    db.flush()


def get_iep_approval(report: ClinicalReport) -> dict[str, Any]:
    return dict(_meta(report).get("iep_approval") or {})


def _default_approval() -> dict[str, Any]:
    return {
        "phase": None,
        "parent_approval_status": None,
        "therapist_approval_status": None,
        "sent_for_parent_approval_at": None,
        "sent_for_therapist_approval_at": None,
        "parent_approval_due_at": None,
        "therapist_approval_due_at": None,
        "review_active": False,
        "ready_for_final_approval": False,
    }


def serialize_iep_approval(report: ClinicalReport) -> dict[str, Any]:
    state = {**_default_approval(), **get_iep_approval(report)}
    return state


def list_review_thread(db: Session, report_id: int) -> list[dict]:
    rows = list(
        db.scalars(
            select(ClinicalReportReviewEvent)
            .where(ClinicalReportReviewEvent.report_id == report_id)
            .order_by(ClinicalReportReviewEvent.created_at.asc())
        ).all()
    )
    return [
        {
            "id": r.id,
            "actor_id": r.actor_id,
            "actor_role": r.actor_role,
            "event_type": r.event_type,
            "comment": r.comment,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "metadata": _json_loads(r.metadata_json),
        }
        for r in rows
        if r.event_type.startswith("iep_") or r.event_type in ("submitted", "returned", "approved", "comment")
    ]


def send_for_stakeholder_approval(db: Session, report: ClinicalReport, cm_user: User) -> dict:
    if report.report_type != "iep":
        raise ValueError("Not an IEP report")
    now = datetime.now(timezone.utc)
    due = now + timedelta(days=AUTO_APPROVE_DAYS)
    meta = _meta(report)
    approval = {
        "phase": "stakeholder",
        "parent_approval_status": "pending",
        "therapist_approval_status": "pending",
        "sent_for_parent_approval_at": now.isoformat(),
        "sent_for_therapist_approval_at": now.isoformat(),
        "parent_approval_due_at": due.isoformat(),
        "therapist_approval_due_at": due.isoformat(),
        "review_active": False,
        "ready_for_final_approval": False,
    }
    meta["iep_approval"] = approval
    _save_meta(db, report, meta)
    report.status = ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value
    report.submitted_at = report.submitted_at or now
    report_status_service.share_report_with_parent(db, report, cm_user)
    report_status_service.log_review_event(
        db, report, cm_user, "iep_sent_for_stakeholder_approval", metadata={"due_days": AUTO_APPROVE_DAYS}
    )
    db.flush()
    return approval


def _stakeholder_side(role: str) -> str:
    if role == "parent":
        return "parent_approval_status"
    if role == "therapist":
        return "therapist_approval_status"
    raise ValueError("Invalid stakeholder role")


def stakeholder_approve(db: Session, report: ClinicalReport, user: User, role: str) -> dict:
    approval = get_iep_approval(report)
    if approval.get("phase") != "stakeholder":
        raise ValueError("IEP is not awaiting stakeholder approval")
    if approval.get("review_active"):
        raise ValueError("A review request is active — wait for case manager to resend")
    key = _stakeholder_side(role)
    if approval.get(key) not in ("pending", None):
        raise ValueError("Already responded")
    approval[key] = "approved"
    meta = _meta(report)
    meta["iep_approval"] = approval
    _recompute_final_ready(approval)
    meta["iep_approval"] = approval
    _save_meta(db, report, meta)
    report_status_service.log_review_event(db, report, user, f"iep_{role}_approved")
    db.flush()
    return approval


def stakeholder_request_review(db: Session, report: ClinicalReport, user: User, role: str, comment: str) -> dict:
    text = (comment or "").strip()
    if len(text) < 5:
        raise ValueError("Share a short reason so the case manager can respond")
    approval = get_iep_approval(report)
    if approval.get("phase") != "stakeholder":
        raise ValueError("IEP is not in stakeholder approval")
    key = _stakeholder_side(role)
    approval[key] = "review_requested"
    approval["review_active"] = True
    approval["ready_for_final_approval"] = False
    meta = _meta(report)
    meta["iep_approval"] = approval
    _save_meta(db, report, meta)
    report_status_service.log_review_event(
        db, report, user, f"iep_{role}_review_requested", comment=text, metadata={"role": role}
    )
    db.flush()
    return approval


def cm_resend_for_approval(db: Session, report: ClinicalReport, cm_user: User, reply: str) -> dict:
    text = (reply or "").strip()
    if len(text) < 5:
        raise ValueError("Add a note explaining what changed before resending")
    now = datetime.now(timezone.utc)
    due = now + timedelta(days=AUTO_APPROVE_DAYS)
    approval = get_iep_approval(report)
    approval.update(
        {
            "phase": "stakeholder",
            "parent_approval_status": "pending",
            "therapist_approval_status": "pending",
            "sent_for_parent_approval_at": now.isoformat(),
            "sent_for_therapist_approval_at": now.isoformat(),
            "parent_approval_due_at": due.isoformat(),
            "therapist_approval_due_at": due.isoformat(),
            "review_active": False,
            "ready_for_final_approval": False,
        }
    )
    meta = _meta(report)
    meta["iep_approval"] = approval
    _save_meta(db, report, meta)
    report_status_service.log_review_event(db, report, cm_user, "iep_cm_resent", comment=text)
    db.flush()
    return approval


def _is_done(status: str | None) -> bool:
    return status in ("approved", "auto_approved")


def _recompute_final_ready(approval: dict) -> None:
    if approval.get("review_active"):
        approval["ready_for_final_approval"] = False
        return
    parent_ok = _is_done(approval.get("parent_approval_status"))
    therapist_ok = _is_done(approval.get("therapist_approval_status"))
    approval["ready_for_final_approval"] = parent_ok and therapist_ok


def apply_iep_auto_approvals(db: Session, *, now: datetime | None = None) -> dict:
    """Idempotent — auto-approve pending stakeholder sides after due date."""
    now = now or datetime.now(timezone.utc)
    reports = list(
        db.scalars(
            select(ClinicalReport).where(
                ClinicalReport.report_type == "iep",
                ClinicalReport.archived_at.is_(None),
                ClinicalReport.status == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value,
            )
        ).all()
    )
    parent_auto = 0
    therapist_auto = 0
    for report in reports:
        meta = _meta(report)
        approval = meta.get("iep_approval") or {}
        if approval.get("phase") != "stakeholder" or approval.get("review_active"):
            continue
        changed = False
        if approval.get("parent_approval_status") == "pending":
            due_raw = approval.get("parent_approval_due_at")
            if due_raw:
                due = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
                if now >= due:
                    approval["parent_approval_status"] = "auto_approved"
                    parent_auto += 1
                    changed = True
        if approval.get("therapist_approval_status") == "pending":
            due_raw = approval.get("therapist_approval_due_at")
            if due_raw:
                due = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
                if now >= due:
                    approval["therapist_approval_status"] = "auto_approved"
                    therapist_auto += 1
                    changed = True
        if changed:
            _recompute_final_ready(approval)
            meta["iep_approval"] = approval
            _save_meta(db, report, meta)
    if parent_auto or therapist_auto:
        db.flush()
    return {"parent_auto_approved": parent_auto, "therapist_auto_approved": therapist_auto}
