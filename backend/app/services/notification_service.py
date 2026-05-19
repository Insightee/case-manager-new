from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    db: Session,
    *,
    user_id: int,
    title: str,
    body: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> Notification:
    n = Notification(user_id=user_id, title=title, body=body, entity_type=entity_type, entity_id=entity_id)
    db.add(n)
    db.flush()
    return n


def list_notifications(db: Session, user_id: int) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
        ).all()
    )
