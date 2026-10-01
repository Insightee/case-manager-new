"""HR alerts and email when staff probation periods end."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.models.role import Role
from app.models.user import User
from app.services import staff_employment_service as employment

logger = logging.getLogger(__name__)


def _hr_recipient_emails(db: Session) -> list[str]:
    hr_role = db.scalars(select(Role).where(Role.name == RoleName.HR.value)).first()
    if not hr_role:
        return []
    emails: list[str] = []
    for user in hr_role.users or []:
        if user.email and user.is_active:
            emails.append(user.email.lower())
    return sorted(set(emails))


def process_probation_end_notifications(db: Session) -> list[dict]:
    """Mark probation-ended staff and notify HR (idempotent per user)."""
    pending = employment.staff_users_pending_probation_notification(db)
    if not pending:
        return []

    hr_emails = _hr_recipient_emails(db)
    alerts: list[dict] = []
    now = datetime.now(timezone.utc)

    for staff in pending:
        end = employment.probation_end_date(staff)
        if not end:
            continue
        staff.staff_probation_end_notified_at = now
        message = (
            f"{staff.full_name}'s probation ended on {end.strftime('%d %b %Y')}. "
            "Please update their employment type to Employee or Consultant."
        )
        alerts.append(
            {
                "staff_user_id": staff.id,
                "staff_name": staff.full_name,
                "staff_email": staff.email,
                "probation_end_date": end.isoformat(),
                "message": message,
            }
        )
        for email in hr_emails:
            try:
                from app.services.email import service as email_service

                email_service.send_email(
                    to=email,
                    subject=f"Probation ended — {staff.full_name}",
                    body_text=message + f"\n\nReview in People: staff profile for {staff.email}",
                    db=db,
                )
            except Exception:
                logger.exception("Failed to send probation end email to %s for user %s", email, staff.id)

    return alerts


def probation_end_alerts_for_hr(db: Session) -> list[dict]:
    """Dashboard alerts for HR — includes ended probations still typed as Probation."""
    if not employment.staff_users_with_ended_probation(db):
        return []
    rows = employment.staff_users_with_ended_probation(db)
    alerts: list[dict] = []
    for staff in rows:
        end = employment.probation_end_date(staff)
        if not end:
            continue
        alerts.append(
            {
                "id": f"probation_end_{staff.id}",
                "severity": "warning",
                "title": "Probation ended — update employment type",
                "message": f"{staff.full_name} (ended {end.strftime('%d %b %Y')}) — change from Probation to Employee or Consultant.",
                "href": f"/admin/people?tab=staff&staffId={staff.id}",
            }
        )
    return alerts
