from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_my_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = notification_service.list_notifications(db, user.id, limit=limit, unread_only=unread_only)
    unread = notification_service.unread_count(db, user.id)
    return {
        "notifications": [
            NotificationRead(
                id=n.id,
                title=n.title,
                body=n.body,
                is_read=n.is_read,
                created_at=n.created_at,
                entity_type=n.entity_type,
                entity_id=n.entity_id,
            )
            for n in rows
        ],
        "unread_count": unread,
    }


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = notification_service.mark_notification_read(db, notification_id, user.id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.commit()
    return {"status": "read"}


@router.patch("/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = notification_service.mark_all_read(db, user.id)
    db.commit()
    return {"marked": n}
