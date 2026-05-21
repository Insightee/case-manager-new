from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import RoleName
from app.models.case import Case, CaseStatus
from app.models.session import SessionMode
from app.models.user import InviteToken, User
from app.services import (
    appointment_notification_service as appt_notify,
    assignment_service,
    case_code_service,
    family_admin_service,
    session_service,
)


def _split_child_name(child_name: str) -> tuple[str, str]:
    parts = child_name.strip().split(None, 1)
    if not parts:
        return "Child", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def create_walk_in_manual_session(
    db: Session,
    *,
    therapist_user_id: int,
    therapist_name: str,
    client_name: str,
    client_email: str,
    child_name: str,
    client_phone: str | None,
    scheduled_date: date,
    actual_start_at: datetime,
    actual_end_at: datetime,
    mode: SessionMode,
    product_module: str = "homecare",
) -> dict:
    email = client_email.lower().strip()
    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing:
        raise ValueError("A user with this email already exists")

    child_label = (child_name or client_name).strip()
    child_first, child_last = _split_child_name(child_label)
    child = family_admin_service.create_child(db, child_first, child_last or "—")

    case_code = case_code_service.generate_case_code(db, product_module)
    service_label = product_module.replace("_", " ").title()
    case = Case(
        case_code=case_code,
        child_id=child.id,
        service_type=service_label,
        product_module=product_module,
        status=CaseStatus.PENDING_ALLOTMENT,
        notes=f"Walk-in intake by therapist (forgotten session log). Parent: {client_name.strip()}",
    )
    db.add(case)
    db.flush()

    assignment_service.create_assignment(
        db,
        case_id=case.id,
        therapist_user_id=therapist_user_id,
        assigned_by_user_id=therapist_user_id,
        start_date=scheduled_date,
        reason_for_change="Provisional assignment — walk-in intake pending admin allotment",
    )

    token = secrets.token_urlsafe(32)
    invite = InviteToken(
        email=email,
        role_name=RoleName.PARENT.value,
        module_assignments=[],
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_user_id=therapist_user_id,
        linked_child_id=child.id,
        invite_metadata={
            "pending_case_id": case.id,
            "therapist_user_id": therapist_user_id,
            "intake_source": "forgot_session",
            "client_name": client_name.strip(),
            "child_name": child_label,
            "client_phone": client_phone.strip() if client_phone else None,
        },
    )
    db.add(invite)
    db.flush()

    invite_url = f"{settings.frontend_url}/invite/{token}"
    family_admin_service._send_parent_invite_email(
        email,
        invite_url,
        client_name.strip(),
        child.full_name,
    )

    when_label = f"forgotten session log · {scheduled_date.isoformat()}"
    appt_notify.notify_admins_walk_in_invite(
        db,
        therapist_name=therapist_name,
        client_name=child_label,
        client_email=email,
        slot_when=when_label,
    )

    session = session_service.create_manual_session(
        db,
        case_id=case.id,
        therapist_user_id=therapist_user_id,
        scheduled_date=scheduled_date,
        actual_start_at=actual_start_at,
        actual_end_at=actual_end_at,
        mode=mode,
    )

    return {
        "case": case,
        "session": session,
        "invite_url": invite_url,
        "invite_sent": True,
    }
