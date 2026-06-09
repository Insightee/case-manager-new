"""HR / payroll therapist (employee) identifiers on users.external_employee_id."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def normalize_external_employee_id(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def assert_external_employee_id_available(
    db: Session,
    external_id: str | None,
    *,
    exclude_user_id: int | None = None,
) -> None:
    normalized = normalize_external_employee_id(external_id)
    if not normalized:
        return
    stmt = select(User.id).where(User.external_employee_id == normalized)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    if db.scalar(stmt):
        raise ValueError(f"Therapist ID '{normalized}' is already assigned to another user")


def apply_external_employee_id(user: User, external_id: str | None) -> None:
    user.external_employee_id = normalize_external_employee_id(external_id)
