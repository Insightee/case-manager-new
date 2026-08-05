"""Staff escalation targets — search, departments, and department queues."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.departments import staff_department_label, staff_departments_for_api, validate_staff_department
from app.models.role import Role, user_roles
from app.models.user import User

STAFF_ESCALATION_EXCLUDED_ROLES = frozenset({"THERAPIST", "PARENT", "SCHOOL_COORDINATOR"})


def _staff_escalation_base_stmt():
    excluded_user_ids = (
        select(user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(Role.name.in_(STAFF_ESCALATION_EXCLUDED_ROLES))
        .distinct()
    )
    return select(User).where(User.is_active.is_(True), User.id.not_in(excluded_user_ids))


def list_staff_escalation_targets(
    db: Session,
    *,
    search: str | None = None,
    department: str | None = None,
    limit: int = 500,
) -> list[User]:
    stmt = _staff_escalation_base_stmt()
    if department:
        dept_id = validate_staff_department(department)
        if dept_id:
            stmt = stmt.where(User.department == dept_id)
    q = (search or "").strip().lower()
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                func.lower(User.full_name).like(pattern),
                func.lower(User.email).like(pattern),
            )
        )
    stmt = stmt.order_by(User.full_name.asc(), User.email.asc()).limit(limit)
    return list(db.scalars(stmt).all())


def list_staff_in_department(db: Session, department_id: str) -> list[User]:
    dept_id = validate_staff_department(department_id)
    if not dept_id:
        return []
    return list_staff_escalation_targets(db, department=dept_id)


def escalation_targets_payload(db: Session, *, search: str | None = None, department: str | None = None) -> dict:
    staff = list_staff_escalation_targets(db, search=search, department=department)
    departments = staff_departments_for_api()
    counts: dict[str, int] = {}
    if not search and not department:
        rows = db.execute(
            select(User.department, func.count(User.id))
            .where(User.is_active.is_(True), User.department.is_not(None))
            .group_by(User.department)
        ).all()
        counts = {str(dept): int(n) for dept, n in rows if dept}

    return {
        "departments": [
            {**d, "member_count": counts.get(d["id"], 0)}
            for d in departments
        ],
        "staff": [
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "department": u.department,
                "department_label": staff_department_label(u.department),
                "roles": list(u.role_names or []),
            }
            for u in staff
        ],
    }


def user_can_pick_up_department_ticket(user: User, ticket_department: str | None) -> bool:
    if not ticket_department or not user.is_active:
        return False
    if "SUPER_ADMIN" in user.role_names:
        return True
    return (user.department or "").upper() == str(ticket_department).upper()
