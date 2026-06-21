"""CRUD and workflow for clinical snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_snapshot import ClinicalSnapshot, ClinicalSnapshotFeedback
from app.models.user import User
from app.core.permissions import user_has_permission

VALID_STATUSES = frozenset({"draft", "saved", "sent_for_review", "approved", "rejected", "archived"})
VALID_INSIGHT_TYPES = frozenset(
    {
        "full_snapshot",
        "goal_suggestions",
        "strategy_review",
        "supports_accommodations",
        "what_not_working",
        "parent_safe_draft",
        "report_support",
        "session_log_support",
        "iep_support",
    }
)
VALID_FEEDBACK = frozenset(
    {
        "useful",
        "not_useful",
        "edited",
        "saved",
        "sent_for_review",
        "approved",
        "rejected",
        "added_to_report",
        "added_to_session_plan",
    }
)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def snapshot_to_dict(snap: ClinicalSnapshot) -> dict[str, Any]:
    ai_json = None
    if snap.ai_output_json:
        try:
            ai_json = json.loads(snap.ai_output_json)
        except json.JSONDecodeError:
            ai_json = None
    det = None
    if snap.deterministic_summary_json:
        try:
            det = json.loads(snap.deterministic_summary_json)
        except json.JSONDecodeError:
            det = None
    return {
        "id": snap.id,
        "case_id": snap.case_id,
        "month": snap.month,
        "year": snap.year,
        "insight_type": snap.insight_type,
        "status": snap.status,
        "ai_output_json": ai_json,
        "ai_output_text": snap.ai_output_text,
        "input_hash": snap.input_hash,
        "provider": snap.provider,
        "model": snap.model,
        "requires_review": (ai_json or {}).get("requires_review", True),
        "parent_safe": (ai_json or {}).get("parent_safe", False),
        "deterministic_summary": det,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
        "updated_at": snap.updated_at.isoformat() if snap.updated_at else None,
    }


def find_existing(
    db: Session,
    *,
    case_id: int,
    month: str,
    insight_type: str,
    input_hash: str,
) -> ClinicalSnapshot | None:
    return db.scalars(
        select(ClinicalSnapshot)
        .where(
            ClinicalSnapshot.case_id == case_id,
            ClinicalSnapshot.month == month,
            ClinicalSnapshot.insight_type == insight_type,
            ClinicalSnapshot.input_hash == input_hash,
        )
        .order_by(ClinicalSnapshot.id.desc())
        .limit(1)
    ).first()


def create_snapshot(
    db: Session,
    *,
    case_id: int,
    month: str,
    user: User,
    insight_type: str,
    deterministic_summary: dict[str, Any],
    ai_output: dict[str, Any],
    input_hash: str,
    provider: str,
    model: str | None,
    reference_chunk_ids: list[int] | None = None,
    generation_log_id: int | None = None,
    token_input: int | None = None,
    token_output: int | None = None,
    estimated_cost: float | None = None,
) -> ClinicalSnapshot:
    if insight_type not in VALID_INSIGHT_TYPES:
        raise ValueError(f"Invalid insight_type: {insight_type}")

    ai_text = ai_output.get("snapshot_summary") or ""
    out_hash = _hash_text(json.dumps(ai_output, sort_keys=True, default=str))
    year = int(month[:4])

    snap = ClinicalSnapshot(
        case_id=case_id,
        month=month,
        year=year,
        generated_by_user_id=user.id,
        generated_for_role=getattr(user, "role_name", None) or "therapist",
        insight_type=insight_type,
        status="draft",
        deterministic_summary_json=json.dumps(deterministic_summary, default=str),
        ai_output_json=json.dumps(ai_output, default=str),
        ai_output_text=ai_text,
        reference_chunk_ids_json=json.dumps(reference_chunk_ids or []),
        prompt_version="v1",
        provider=provider,
        model=model,
        input_hash=input_hash,
        output_hash=out_hash,
        token_input_count=token_input,
        token_output_count=token_output,
        estimated_cost=estimated_cost,
        generation_log_id=generation_log_id,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def list_snapshots(db: Session, case_id: int, month: str | None = None) -> list[dict[str, Any]]:
    q = select(ClinicalSnapshot).where(ClinicalSnapshot.case_id == case_id)
    if month:
        q = q.where(ClinicalSnapshot.month == month)
    q = q.order_by(ClinicalSnapshot.id.desc())
    return [snapshot_to_dict(s) for s in db.scalars(q).all()]


def get_snapshot(db: Session, snapshot_id: int, case_id: int) -> ClinicalSnapshot:
    snap = db.get(ClinicalSnapshot, snapshot_id)
    if not snap or snap.case_id != case_id:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


def add_feedback(
    db: Session,
    snap: ClinicalSnapshot,
    user: User,
    feedback_type: str,
    comment: str | None = None,
) -> None:
    if feedback_type not in VALID_FEEDBACK:
        raise HTTPException(status_code=400, detail="Invalid feedback type")
    db.add(
        ClinicalSnapshotFeedback(
            snapshot_id=snap.id,
            user_id=user.id,
            feedback_type=feedback_type,
            comment=comment,
        )
    )
    if feedback_type == "saved":
        snap.status = "saved"
    elif feedback_type == "sent_for_review":
        snap.status = "sent_for_review"
    elif feedback_type == "approved":
        snap.status = "approved"
    elif feedback_type == "rejected":
        snap.status = "rejected"
    db.commit()


def send_for_review(db: Session, snap: ClinicalSnapshot, user: User) -> None:
    snap.status = "sent_for_review"
    db.add(
        ClinicalSnapshotFeedback(
            snapshot_id=snap.id,
            user_id=user.id,
            feedback_type="sent_for_review",
        )
    )
    db.commit()


def approve_snapshot(db: Session, snap: ClinicalSnapshot, user: User, comment: str | None = None) -> None:
    if not user_has_permission(user, "monthly_report.approve"):
        raise HTTPException(status_code=403, detail="Only case managers can approve snapshots")
    snap.status = "approved"
    db.add(
        ClinicalSnapshotFeedback(
            snapshot_id=snap.id,
            user_id=user.id,
            feedback_type="approved",
            comment=comment,
        )
    )
    db.commit()


def reject_snapshot(db: Session, snap: ClinicalSnapshot, user: User, comment: str | None = None) -> None:
    if not user_has_permission(user, "monthly_report.approve"):
        raise HTTPException(status_code=403, detail="Only case managers can reject snapshots")
    snap.status = "rejected"
    db.add(
        ClinicalSnapshotFeedback(
            snapshot_id=snap.id,
            user_id=user.id,
            feedback_type="rejected",
            comment=comment,
        )
    )
    db.commit()
