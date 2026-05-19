from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import RoleName, case_scope_check
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.parent import ParentGuardian
from app.models.user import User

router = APIRouter(prefix="/files", tags=["files"])


def _can_view_avatar(db: Session, viewer: User, target_user_id: int) -> bool:
    if viewer.id == target_user_id:
        return True
    if "case.read.all" in viewer.permission_names or "therapist.read" in viewer.permission_names:
        return True
    if RoleName.PARENT.value in viewer.role_names:
        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == viewer.id)).first()
        if pg:
            child_ids = [c.id for c in pg.children]
            case_ids = [c.id for c in db.scalars(select(Case).where(Case.child_id.in_(child_ids))).all()]
            if case_ids:
                assigned = db.scalars(
                    select(CaseAssignment).where(
                        CaseAssignment.case_id.in_(case_ids),
                        CaseAssignment.therapist_user_id == target_user_id,
                        CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                    )
                ).first()
                if assigned:
                    return True
    if "case.read.assigned" in viewer.permission_names:
        for assignment in db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == viewer.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).all():
            case = db.get(Case, assignment.case_id)
            if case and case_scope_check(db, viewer, case):
                other = db.scalars(
                    select(CaseAssignment).where(
                        CaseAssignment.case_id == case.id,
                        CaseAssignment.therapist_user_id == target_user_id,
                        CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                    )
                ).first()
                if other:
                    return True
    return False


@router.get("/avatars/{user_id}")
def get_avatar(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _can_view_avatar(db, user, user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    target = db.get(User, user_id)
    if not target or not target.avatar_path:
        raise HTTPException(status_code=404, detail="Avatar not found")
    path = Path(target.avatar_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Avatar file missing")
    media = "image/jpeg"
    if path.suffix.lower() == ".png":
        media = "image/png"
    elif path.suffix.lower() == ".webp":
        media = "image/webp"
    return FileResponse(path, media_type=media)
