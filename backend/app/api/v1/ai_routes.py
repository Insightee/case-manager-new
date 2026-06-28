from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import case_scope_check, require_permission, user_has_permission
from app.models.user import User
from app.services import ai_gateway_service as ai_svc
from app.services import case_service

router = APIRouter(prefix="/ai", tags=["ai"])


class AiPreviewRequest(BaseModel):
    action: str = Field(min_length=3, max_length=64)
    case_id: Optional[int] = None
    context: dict[str, Any] = Field(default_factory=dict)
    target_type: str = "generic"
    target_id: Optional[int] = None


@router.post("/preview")
def ai_preview(
    payload: AiPreviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "monthly_report.create") and not user_has_permission(user, "monthly_report.approve"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if payload.case_id:
        case = case_service.get_case(db, payload.case_id)
        if not case or not case_scope_check(db, user, case):
            raise HTTPException(status_code=404, detail="Case not found")
        ctx = dict(payload.context)
        ctx.setdefault("child_name", case.child_name if hasattr(case, "child_name") else None)
        ctx.setdefault("case_code", case.case_code if hasattr(case, "case_code") else None)
    else:
        ctx = payload.context

    return ai_svc.AIGatewayService.preview(
        db,
        user_id=user.id,
        case_id=payload.case_id,
        action=payload.action,
        context=ctx,
        target_type=payload.target_type,
        target_id=payload.target_id,
    )
