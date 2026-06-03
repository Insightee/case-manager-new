from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.email_suppression import EmailSuppression
from app.models.user import User


def normalize_email(email: str) -> str:
    return email.lower().strip()


def get_active_suppression(db: Session, email: str) -> EmailSuppression | None:
    email_l = normalize_email(email)
    if not email_l:
        return None
    row = db.scalars(
        select(EmailSuppression).where(
            EmailSuppression.email == email_l,
            EmailSuppression.cleared_at.is_(None),
        )
    ).first()
    return row


def is_suppressed(db: Session, email: str) -> bool:
    return get_active_suppression(db, email) is not None


def suppress_email(
    db: Session,
    email: str,
    *,
    reason: str,
    source: str,
    notes: str | None = None,
) -> EmailSuppression:
    email_l = normalize_email(email)
    existing = get_active_suppression(db, email_l)
    now = datetime.now(timezone.utc)
    if existing:
        existing.reason = reason
        existing.source = source
        if notes:
            existing.notes = notes
        existing.updated_at = now
        db.flush()
        return existing
    row = EmailSuppression(
        email=email_l,
        reason=reason,
        source=source,
        notes=notes,
        suppressed_at=now,
    )
    db.add(row)
    db.flush()
    return row


def clear_suppression(
    db: Session,
    email: str,
    *,
    cleared_by_user_id: int,
    clear_reason: str,
    corrected_email: str | None = None,
) -> EmailSuppression | None:
    email_l = normalize_email(email)
    row = get_active_suppression(db, email_l)
    if not row:
        return None
    now = datetime.now(timezone.utc)
    row.cleared_at = now
    row.cleared_by = cleared_by_user_id
    note = f"Cleared: {clear_reason.strip()}"
    if corrected_email:
        note += f" (corrected to {normalize_email(corrected_email)})"
    row.notes = (row.notes or "") + ("\n" if row.notes else "") + note
    row.updated_at = now
    db.flush()
    return row


def linked_user_count(db: Session, email: str) -> int:
    email_l = normalize_email(email)
    return int(
        db.scalar(select(func.count()).select_from(User).where(User.email == email_l)) or 0
    )
