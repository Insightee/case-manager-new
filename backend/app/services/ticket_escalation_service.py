from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import RoleName
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.support_ticket import SupportTicket, TicketCategory, TicketTopic
from app.models.user import User

# Topic → primary category for reporting
TOPIC_CATEGORY: dict[TicketTopic, TicketCategory] = {
    TicketTopic.BILLING_PAYMENT: TicketCategory.FINANCE,
    TicketTopic.THERAPIST: TicketCategory.SERVICE,
    TicketTopic.CASE_MANAGER: TicketCategory.SERVICE,
    TicketTopic.OTHER: TicketCategory.OTHER,
}

# When topic is omitted (defaults to OTHER), infer routing from staff-selected category.
CATEGORY_ROUTING_TOPIC: dict[TicketCategory, TicketTopic] = {
    TicketCategory.FINANCE: TicketTopic.BILLING_PAYMENT,
}

# Escalation matrix: each topic has an ordered list of roles (L1 → L2 → L3)
ESCALATION_MATRIX: dict[TicketTopic, list[str]] = {
    TicketTopic.BILLING_PAYMENT: [
        RoleName.FINANCE.value,
        RoleName.ADMIN.value,
        RoleName.SUPER_ADMIN.value,
    ],
    TicketTopic.THERAPIST: [
        RoleName.CASE_MANAGER.value,
        RoleName.HR.value,
        RoleName.ADMIN.value,
    ],
    TicketTopic.CASE_MANAGER: [
        RoleName.CASE_MANAGER.value,
        RoleName.SUPERVISOR.value,
        RoleName.ADMIN.value,
    ],
    TicketTopic.OTHER: [
        RoleName.ADMIN.value,
        RoleName.SUPER_ADMIN.value,
    ],
}

TOPIC_LABELS = {
    TicketTopic.BILLING_PAYMENT: "Billing / payment",
    TicketTopic.THERAPIST: "Therapist related",
    TicketTopic.CASE_MANAGER: "Case manager",
    TicketTopic.OTHER: "Other",
}


def topic_from_str(value: str) -> TicketTopic:
    try:
        return TicketTopic(value)
    except ValueError:
        return TicketTopic.OTHER


def escalation_roles(topic: TicketTopic) -> list[str]:
    return ESCALATION_MATRIX.get(topic, ESCALATION_MATRIX[TicketTopic.OTHER])


def ticket_visible_to_hr_desk(ticket: SupportTicket) -> bool:
    """HR desk: therapist-chain tickets and HR-category items."""
    if ticket.category == TicketCategory.HR:
        return True
    return ticket.topic == TicketTopic.THERAPIST


def ticket_visible_to_finance_desk(ticket: SupportTicket, *, user_id: int) -> bool:
    """Finance desk: billing-topic/category or self-raised."""
    if ticket.raised_by_user_id == user_id:
        return True
    if ticket.assigned_to_user_id == user_id:
        return True
    if ticket.category == TicketCategory.FINANCE:
        return True
    return ticket.topic == TicketTopic.BILLING_PAYMENT


def finance_desk_ticket_clause(user_id: int):
    """SQL filter for finance desk ticket queues."""
    return or_(
        SupportTicket.raised_by_user_id == user_id,
        SupportTicket.assigned_to_user_id == user_id,
        SupportTicket.category == TicketCategory.FINANCE,
        SupportTicket.topic == TicketTopic.BILLING_PAYMENT,
    )


def hr_desk_ticket_clause(user_id: int):
    """SQL filter for HR desk ticket queues."""
    return or_(
        SupportTicket.raised_by_user_id == user_id,
        SupportTicket.assigned_to_user_id == user_id,
        SupportTicket.category == TicketCategory.HR,
        SupportTicket.topic == TicketTopic.THERAPIST,
    )


def ticket_visible_to_admin_desk(ticket: SupportTicket, *, user_id: int) -> bool:
    """Operations admin desk: general categories only (not finance / HR / clinical chains)."""
    if ticket.raised_by_user_id == user_id or ticket.assigned_to_user_id == user_id:
        return True
    if ticket.category in (TicketCategory.FINANCE, TicketCategory.HR):
        return False
    if ticket.topic in (TicketTopic.BILLING_PAYMENT, TicketTopic.THERAPIST, TicketTopic.CASE_MANAGER):
        return False
    return ticket.category in _ADMIN_DESK_CATEGORIES and ticket.topic == TicketTopic.OTHER


def admin_desk_ticket_clause(user_id: int):
    """SQL filter for operations admin ticket queues."""
    return or_(
        SupportTicket.raised_by_user_id == user_id,
        SupportTicket.assigned_to_user_id == user_id,
        and_(
            SupportTicket.category.in_(tuple(_ADMIN_DESK_CATEGORIES)),
            SupportTicket.topic == TicketTopic.OTHER,
        ),
    )


def normalize_ticket_routing(ticket: SupportTicket) -> None:
    """Map category to topic when the client only sent a desk category (topic still OTHER)."""
    if ticket.topic != TicketTopic.OTHER:
        return
    routed = CATEGORY_ROUTING_TOPIC.get(ticket.category)
    if routed:
        ticket.topic = routed


_ADMIN_DESK_CATEGORIES = frozenset(
    {
        TicketCategory.OTHER,
        TicketCategory.SERVICE,
        TicketCategory.POSH,
        TicketCategory.CPP,
    }
)
_ADMIN_TAG_ROLES = frozenset(
    {RoleName.ADMIN.value, RoleName.MODULE_ADMIN.value, RoleName.SUPER_ADMIN.value}
)
_CM_TAG_ROLES = frozenset({RoleName.CASE_MANAGER.value, RoleName.SUPERVISOR.value})


def role_names_matching_tag(role_tag: str) -> frozenset[str]:
    if role_tag == RoleName.ADMIN.value:
        return _ADMIN_TAG_ROLES
    if role_tag == RoleName.CASE_MANAGER.value:
        return _CM_TAG_ROLES
    return frozenset({role_tag})


def _active_user_id_for_email(db: Session, email: str) -> int | None:
    normalized = (email or "").strip().lower()
    if not normalized:
        return None
    user = db.scalars(
        select(User).where(func.lower(User.email) == normalized, User.is_active.is_(True))
    ).first()
    return user.id if user else None


def resolve_finance_desk_assignee(db: Session) -> int | None:
    uid = _active_user_id_for_email(db, settings.ticket_finance_assignee_email)
    if uid:
        return uid
    return find_assignee_for_role(db, RoleName.FINANCE.value)


def resolve_hr_desk_assignee(db: Session) -> int | None:
    emails = settings.ticket_hr_assignee_email_list
    if emails:
        if len(emails) == 1:
            uid = _active_user_id_for_email(db, emails[0])
            if uid:
                return uid
        else:
            count = int(
                db.scalar(
                    select(func.count()).select_from(SupportTicket).where(
                        SupportTicket.category == TicketCategory.HR
                    )
                )
                or 0
            )
            for offset in range(len(emails)):
                uid = _active_user_id_for_email(db, emails[(count + offset) % len(emails)])
                if uid:
                    return uid
    return find_assignee_for_role(db, RoleName.HR.value)


def resolve_assignee_for_ticket_role(
    db: Session,
    ticket: SupportTicket,
    role_name: str,
    case: Case | None,
    *,
    level: int,
) -> int | None:
    if ticket.category == TicketCategory.HR and level == 0 and role_name != RoleName.CASE_MANAGER.value:
        return resolve_hr_desk_assignee(db)
    if role_name == RoleName.FINANCE.value and level == 0:
        return resolve_finance_desk_assignee(db)
    if role_name == RoleName.HR.value:
        return resolve_hr_desk_assignee(db)
    return find_assignee_for_role(db, role_name, case)


def user_matches_role_tag(user: User, role_tag: str) -> bool:
    names = set(user.role_names)
    return bool(names & role_names_matching_tag(role_tag))


def _module_scoped_for_case(user: User, case: Case | None, role_tag: str) -> bool:
    if not case or not case.product_module:
        return True
    mods = user.module_assignments or []
    if not mods:
        return True
    if case.product_module in mods:
        return True
    if role_tag == RoleName.ADMIN.value:
        return bool(set(user.role_names) & _ADMIN_TAG_ROLES)
    if role_tag in (RoleName.FINANCE.value, RoleName.SUPER_ADMIN.value):
        return True
    return False


def resolve_users_for_role_tag(db: Session, role_tag: str, case: Case | None = None) -> list[int]:
    """All active users matching an incident role tag (ADMIN includes MODULE_ADMIN)."""
    ids: list[int] = []
    if case and role_tag == RoleName.CASE_MANAGER.value and case.case_manager_user_id:
        cm = db.get(User, case.case_manager_user_id)
        if cm and cm.is_active:
            ids.append(cm.id)
    for user in db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.id)).all():
        if user.id in ids:
            continue
        if not user_matches_role_tag(user, role_tag):
            continue
        if not _module_scoped_for_case(user, case, role_tag):
            continue
        ids.append(user.id)
    return ids


def find_assignee_for_role(db: Session, role_name: str, case: Case | None = None) -> int | None:
    """Pick an active user with the role; prefer case manager / module match when relevant."""
    if case and role_name == RoleName.CASE_MANAGER.value and case.case_manager_user_id:
        cm = db.get(User, case.case_manager_user_id)
        if cm and cm.is_active:
            return cm.id

    if case and role_name == RoleName.THERAPIST.value:
        asg = db.scalars(
            select(CaseAssignment)
            .where(
                CaseAssignment.case_id == case.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
            .order_by(CaseAssignment.start_date.desc())
        ).first()
        if asg:
            t = db.get(User, asg.therapist_user_id)
            if t and t.is_active:
                return t.id

    resolved = resolve_users_for_role_tag(db, role_name, case)
    return resolved[0] if resolved else None


def assign_ticket(db: Session, ticket: SupportTicket, case: Case | None = None) -> None:
    normalize_ticket_routing(ticket)
    level = min(ticket.escalation_level or 0, max(len(escalation_roles(ticket.topic)) - 1, 0))

    if ticket.category == TicketCategory.HR and level == 0:
        assignee = resolve_hr_desk_assignee(db)
        if assignee:
            ticket.assigned_to_user_id = assignee
        return

    roles = escalation_roles(ticket.topic)
    role = roles[level]
    assignee = resolve_assignee_for_ticket_role(db, ticket, role, case, level=level)
    if assignee:
        ticket.assigned_to_user_id = assignee
    if ticket.topic != TicketTopic.OTHER:
        ticket.category = TOPIC_CATEGORY.get(ticket.topic, TicketCategory.OTHER)


def escalate_ticket(db: Session, ticket: SupportTicket, case: Case | None = None) -> dict:
    roles = escalation_roles(ticket.topic)
    next_level = (ticket.escalation_level or 0) + 1
    if next_level >= len(roles):
        return {"escalation_level": ticket.escalation_level, "max_level": True}
    ticket.escalation_level = next_level
    from app.models.support_ticket import TicketStatus

    ticket.status = TicketStatus.IN_PROGRESS
    assign_ticket(db, ticket, case)
    return {
        "escalation_level": ticket.escalation_level,
        "assigned_role": roles[next_level],
        "max_level": False,
    }
