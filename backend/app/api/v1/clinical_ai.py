"""Clinical AI helper endpoints — optional, logged, human-reviewed."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.permissions import require_case_access, user_has_permission
from app.models.user import User
from app.schemas.clinical_brain import (
    ClinicalAiLanguageCheckRequest,
    ClinicalAiMonthlyDraftRequest,
    ClinicalAiSessionNoteRequest,
)
from app.services import clinical_ai_service as ai_svc

router = APIRouter(prefix="/clinical-ai", tags=["clinical-ai"])


def _block_parent(user: User) -> None:
    if user_has_permission(user, "parent.portal"):
        raise HTTPException(status_code=403, detail="Not available on parent portal")


@router.post("/session-note/improve")
def improve_session_note(
    payload: ClinicalAiSessionNoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _block_parent(user)
    return ai_svc.improve_session_note(db, user, raw_note=payload.raw_note, context=payload.context)


@router.post("/monthly-report/{report_id}/draft-section")
def draft_monthly_section(
    report_id: int,
    payload: ClinicalAiMonthlyDraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _block_parent(user)
    return ai_svc.draft_monthly_report_section(
        db,
        user,
        report_id=report_id,
        section_type=payload.section_type,
        parent_safe=payload.parent_safe,
    )


@router.post("/iep/suggest-goal-wording")
def suggest_iep_goal_wording(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _block_parent(user)
    return ai_svc.suggest_iep_goal_wording(db, user, payload=payload)


@router.post("/cases/{case_id}/strategy-recommendations")
def strategy_recommendations(
    case_id: int,
    goal_context: dict[str, Any],
    db: Session = Depends(get_db),
    user_case: tuple[User, object] = Depends(require_case_access()),
):
    user, _case = user_case
    return ai_svc.recommend_strategies(db, user, case_id=case_id, goal_context=goal_context)


@router.post("/language-check/parent-safe")
def parent_safe_language_check(
    payload: ClinicalAiLanguageCheckRequest,
    user: User = Depends(get_current_user),
):
    del user
    return ai_svc.check_parent_safe_language(payload.text)
