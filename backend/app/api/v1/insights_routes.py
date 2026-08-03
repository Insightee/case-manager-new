"""Insights Engine API — deterministic preview + on-demand snapshot generation."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.module_write import ensure_case_write_access
from app.core.permissions import RoleName, case_scope_check, user_has_permission
from app.models.user import User
from app.services import ai_gateway_service as ai_svc
from app.services import case_service
from app.services import clinical_insight_summary_service as summary_svc
from app.services import clinical_insights_preview_service as preview_svc
from app.services import clinical_snapshot_service as snap_svc
from app.services import reference_retrieval_service as ref_svc
from app.services.insights import ai_insight_refresh_service as refresh_svc
from app.services.insights import insight_action_service as action_svc
from app.services.insights import insights_ask_service as ask_svc
from app.services.insights import insights_chat_usage_limiter as ask_usage_limiter
from app.services.insights import weekly_insight_usage_limiter as usage_limiter
from app.services.insights.case_insight_aggregator import build_case_insight_payload

router = APIRouter(prefix="/cases/{case_id}/insights", tags=["insights"])


def _block_parent(user: User) -> None:
    if RoleName.PARENT.value in (user.role_names or []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not available for parent accounts")


def _case_for_user(db: Session, user: User, case_id: int):
    _block_parent(user)
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _case_write(db: Session, user: User, case_id: int):
    case = _case_for_user(db, user, case_id)
    ensure_case_write_access(user, case, db)
    return case


class GenerateSnapshotRequest(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    insight_type: str = "full_snapshot"
    force_regenerate: bool = False


class SelectForReportRequest(BaseModel):
    insight_ids: list[str] = Field(min_length=1)
    destination: str = Field(pattern=r"^(monthly_report|iep_review)$")


class FeedbackRequest(BaseModel):
    feedback_type: str
    comment: Optional[str] = None


class RejectRequest(BaseModel):
    comment: Optional[str] = None


class InsightsAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None


@router.get("/data-preview")
def get_data_preview(
    case_id: int,
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    try:
        return preview_svc.build_data_preview(db, case_id, month)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generate-snapshot")
def generate_snapshot(
    case_id: int,
    payload: GenerateSnapshotRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_write(db, user, case_id)

    preview = preview_svc.build_data_preview(db, case_id, payload.month)
    input_hash = preview["input_hash"]

    if not payload.force_regenerate:
        existing = snap_svc.find_existing(
            db,
            case_id=case_id,
            month=payload.month,
            insight_type=payload.insight_type,
            input_hash=input_hash,
        )
        if existing:
            result = snap_svc.snapshot_to_dict(existing)
            result["reused"] = True
            result["message"] = "Using saved snapshot. Source data has not changed."
            return result

    summary = summary_svc.build_monthly_case_summary(db, case_id, payload.month)
    query = f"{payload.insight_type} {payload.month}"
    refs = ref_svc.retrieve_reference_chunks(
        db,
        query=query,
        role="therapist",
        case_id=case_id,
        user_id=user.id,
    )
    role = user.role_names[0] if user.role_names else "therapist"
    gen = ai_svc.AIGatewayService.generate_clinical_snapshot(
        db,
        user_id=user.id,
        case_id=case_id,
        summary=summary,
        insight_type=payload.insight_type,
        role=role,
        references=refs,
    )

    snap = snap_svc.create_snapshot(
        db,
        case_id=case_id,
        month=payload.month,
        user=user,
        insight_type=payload.insight_type,
        deterministic_summary=summary,
        ai_output=gen["output"],
        input_hash=input_hash,
        provider=gen["provider"],
        model=gen["model"],
        reference_chunk_ids=[r["chunk_id"] for r in refs],
        generation_log_id=gen.get("generation_log_id"),
        token_input=gen.get("token_input_count"),
        token_output=gen.get("token_output_count"),
        estimated_cost=gen.get("estimated_cost"),
    )
    result = snap_svc.snapshot_to_dict(snap)
    result["reused"] = False
    if gen["output"].get("provider_warning"):
        result["provider_warning"] = gen["output"]["provider_warning"]
    return result


@router.get("/case-summary")
def get_case_summary(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Always-available, no-AI Insights tab payload — Layer 1 (Structured Insight Engine)."""
    _case_for_user(db, user, case_id)
    try:
        return build_case_insight_payload(db, case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/usage")
def get_refresh_usage(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    return usage_limiter.get_usage(db, case_id=case_id, user_id=user.id)


@router.get("/ask-usage")
def get_ask_usage(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    return ask_usage_limiter.get_usage(db, case_id=case_id, user_id=user.id)


@router.post("/ask")
def ask_insights(
    case_id: int,
    payload: InsightsAskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Case-scoped Ask — explicit send only; compact structured context."""
    _case_write(db, user, case_id)
    try:
        return ask_svc.ask_insight(db, case_id=case_id, user=user, question=payload.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/refresh")
def refresh_insights(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Refresh Insights — Layer 2/3 AI wording polish, capped at 2/week per case/therapist."""
    _case_write(db, user, case_id)
    try:
        return refresh_svc.refresh_insights(db, case_id=case_id, user=user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/select-for-report")
def select_insights_for_report(
    case_id: int,
    payload: SelectForReportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stages selected insight cards into `case_insight_actions` (pending_review) — never writes report text directly."""
    _case_write(db, user, case_id)
    try:
        current = build_case_insight_payload(db, case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    insights_by_id = {i["id"]: i for i in current["insights"]}
    try:
        rows = action_svc.stage_insights_for_review(
            db,
            case_id=case_id,
            user_id=user.id,
            insight_ids=payload.insight_ids,
            destination=payload.destination,
            insights_by_id=insights_by_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"staged": [action_svc.action_to_dict(r) for r in rows]}


@router.get("/snapshots")
def list_snapshots(
    case_id: int,
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    return {"items": snap_svc.list_snapshots(db, case_id, month)}


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(
    case_id: int,
    snapshot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    snap = snap_svc.get_snapshot(db, snapshot_id, case_id)
    return snap_svc.snapshot_to_dict(snap)


@router.post("/snapshots/{snapshot_id}/feedback")
def snapshot_feedback(
    case_id: int,
    snapshot_id: int,
    payload: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_write(db, user, case_id)
    snap = snap_svc.get_snapshot(db, snapshot_id, case_id)
    if payload.feedback_type == "approved":
        snap_svc.approve_snapshot(db, snap, user, payload.comment)
    elif payload.feedback_type == "rejected":
        snap_svc.reject_snapshot(db, snap, user, payload.comment)
    else:
        snap_svc.add_feedback(db, snap, user, payload.feedback_type, payload.comment)
    return snap_svc.snapshot_to_dict(snap)


@router.post("/snapshots/{snapshot_id}/send-review")
def send_snapshot_review(
    case_id: int,
    snapshot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_write(db, user, case_id)
    snap = snap_svc.get_snapshot(db, snapshot_id, case_id)
    snap_svc.send_for_review(db, snap, user)
    return snap_svc.snapshot_to_dict(snap)


@router.post("/snapshots/{snapshot_id}/approve")
def approve_snapshot(
    case_id: int,
    snapshot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    if not user_has_permission(user, "monthly_report.approve"):
        raise HTTPException(status_code=403, detail="Only case managers can approve snapshots")
    snap = snap_svc.get_snapshot(db, snapshot_id, case_id)
    snap_svc.approve_snapshot(db, snap, user)
    return snap_svc.snapshot_to_dict(snap)


@router.post("/snapshots/{snapshot_id}/reject")
def reject_snapshot(
    case_id: int,
    snapshot_id: int,
    payload: RejectRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    snap = snap_svc.get_snapshot(db, snapshot_id, case_id)
    snap_svc.reject_snapshot(db, snap, user, payload.comment)
    return snap_svc.snapshot_to_dict(snap)
