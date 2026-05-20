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


def list_notifications(db: Session, user_id: int, *, limit: int = 50, unread_only: bool = False) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def unread_count(db: Session, user_id: int) -> int:
    from sqlalchemy import func

    n = db.scalar(
        select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.is_read.is_(False))
    )
    return int(n or 0)


def mark_notification_read(db: Session, notification_id: int, user_id: int) -> Notification | None:
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user_id:
        return None
    n.is_read = True
    db.flush()
    return n


def mark_all_read(db: Session, user_id: int) -> int:
    rows = db.scalars(select(Notification).where(Notification.user_id == user_id, Notification.is_read.is_(False))).all()
    for n in rows:
        n.is_read = True
    db.flush()
    return len(rows)
