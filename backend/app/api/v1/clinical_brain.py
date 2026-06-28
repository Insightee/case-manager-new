"""Clinical Brain HTTP routes — feedback, review queue, IEP evidence, language check."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.permissions import require_case_access, user_has_permission
from app.models.user import User
from app.schemas.clinical_brain import (
    LanguageCheckRequest,
    LanguageCheckResponse,
    StrategyRecommendationFeedbackCreate,
    StrategyRecommendationFeedbackPatch,
    UnifiedReviewQueueAction,
)
from app.services import (
    clinical_brain_suggestion_service as brain_svc,
    clinical_review_queue_service as queue_svc,
    iep_evidence_review_service as iep_review_svc,
    strategy_recommendation_feedback_service as feedback_svc,
)

router = APIRouter(prefix="/clinical-brain", tags=["clinical-brain"])


def _require_cm_admin(user: User) -> None:
    if not (
        user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "admin.override")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CM or admin access required")


@router.post("/check-language", response_model=LanguageCheckResponse)
def check_language(payload: LanguageCheckRequest, user: User = Depends(get_current_user)):
    del user
    result = brain_svc.check_neuroaffirming_language(payload.text)
    return LanguageCheckResponse.model_validate(result)


@router.post("/cases/{case_id}/strategy-recommendation-feedback")
def create_strategy_feedback(
    case_id: int,
    payload: StrategyRecommendationFeedbackCreate,
    db: Session = Depends(get_db),
    user_case: tuple[User, object] = Depends(require_case_access()),
):
    user, case = user_case
    data = payload.model_dump()
    data["case_id"] = case_id
    return feedback_svc.create_feedback(db, case=case, user=user, payload=data)


@router.patch("/cases/{case_id}/strategy-recommendation-feedback/{feedback_id}")
def patch_strategy_feedback(
    case_id: int,
    feedback_id: int,
    payload: StrategyRecommendationFeedbackPatch,
    db: Session = Depends(get_db),
    user_case: tuple[User, object] = Depends(require_case_access()),
):
    user, case = user_case
    del case_id
    return feedback_svc.patch_feedback(
        db,
        feedback_id=feedback_id,
        case=case,
        user=user,
        payload=payload.model_dump(exclude_unset=True),
    )


@router.get("/cases/{case_id}/strategy-recommendation-feedback")
def list_strategy_feedback(
    case_id: int,
    goal_repository_item_id: Optional[int] = None,
    goal_card_id: Optional[int] = None,
    strategy_repository_item_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user_case: tuple[User, object] = Depends(require_case_access()),
):
    del user_case
    return {
        "items": feedback_svc.list_feedback_for_case(
            db,
            case_id,
            goal_repository_item_id=goal_repository_item_id,
            goal_card_id=goal_card_id,
            strategy_repository_item_id=strategy_repository_item_id,
        )
    }


@router.get("/review-queue")
def list_unified_review_queue(
    status: Optional[str] = None,
    item_type: Optional[str] = None,
    priority: Optional[str] = None,
    case_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_cm_admin(user)
    queue_svc.sync_repository_candidates_to_queue(db)
    return {"items": queue_svc.list_queue_items(db, status=status, item_type=item_type, priority=priority, case_id=case_id)}


@router.post("/review-queue/{item_id}/action")
def apply_review_queue_action(
    item_id: int,
    payload: UnifiedReviewQueueAction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_cm_admin(user)
    return queue_svc.apply_queue_action(
        db,
        item_id=item_id,
        actor=user,
        action=payload.action,
        reviewer_note=payload.reviewer_note,
        linked_library_goal_id=payload.linked_library_goal_id,
        linked_library_strategy_id=payload.linked_library_strategy_id,
        revision_request=payload.revision_request,
        parent_safe=payload.parent_safe,
    )


@router.get("/cases/{case_id}/iep-evidence-review")
def get_iep_evidence_review(
    case_id: int,
    iep_plan_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user_case: tuple[User, object] = Depends(require_case_access()),
):
    del user_case
    return iep_review_svc.build_iep_evidence_review(db, case_id=case_id, iep_plan_id=iep_plan_id)


@router.post("/iep-review-suggestions/{suggestion_id}/send-to-review")
def send_iep_suggestion_to_review(
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_cm_admin(user)
    try:
        return iep_review_svc.send_suggestion_to_review(db, suggestion_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
