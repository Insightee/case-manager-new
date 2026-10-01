"""Read-only support ticket report.

Aggregates live tickets and replies for a date range. The payload never includes
message text, attachment contents, child names, parent contacts, or bank details.
POSH and CPP stay in the count tables and are left out of the live queue.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.timezone import IST, ensure_utc_aware, today_ist
from app.models.case import Case
from app.models.support_ticket import SupportTicket, TicketCategory, TicketMessage, TicketStatus
from app.models.user import User
from app.services.reports_export_service import payload_to_xlsx
from app.services.support_ticket_question_groups import QUESTION_GROUPS, classify_question
from app.services.ticket_list_service import staff_ticket_visibility_clause

QUEUE_ROW_LIMIT = 500
_MAX_RANGE_DAYS = 800
_ID_CHUNK = 500

STATUS_ORDER: tuple[TicketStatus, ...] = (
    TicketStatus.OPEN,
    TicketStatus.IN_PROGRESS,
    TicketStatus.RESOLVED,
    TicketStatus.CLOSED,
)
STATUS_LABELS = {
    TicketStatus.OPEN: "Open",
    TicketStatus.IN_PROGRESS: "In progress",
    TicketStatus.RESOLVED: "Resolved",
    TicketStatus.CLOSED: "Closed",
}

CATEGORY_ORDER: tuple[TicketCategory, ...] = (
    TicketCategory.FINANCE,
    TicketCategory.HR,
    TicketCategory.OTHER,
    TicketCategory.SERVICE,
    TicketCategory.TECH,
    TicketCategory.CPP,
    TicketCategory.POSH,
)
CATEGORY_LABELS = {
    TicketCategory.FINANCE: "Finance",
    TicketCategory.HR: "HR",
    TicketCategory.OTHER: "Other",
    TicketCategory.SERVICE: "Service",
    TicketCategory.TECH: "Tech",
    TicketCategory.CPP: "CPP",
    TicketCategory.POSH: "POSH",
}
RESTRICTED_CATEGORIES = frozenset({TicketCategory.POSH, TicketCategory.CPP})

MODULE_ORDER: tuple[str, ...] = ("shadow_support", "homecare", "b2b", "none")
MODULE_LABELS = {
    "shadow_support": "Shadow support",
    "homecare": "Homecare",
    "b2b": "B2B",
    "none": "None",
}

ROLE_LABELS = {
    "SUPER_ADMIN": "Super admin",
    "ADMIN": "Admin",
    "MODULE_ADMIN": "Module admin",
    "VIEWER": "Viewer",
    "CASE_MANAGER": "Case manager",
    "SUPERVISOR": "Supervisor",
    "THERAPIST": "Therapist",
    "FINANCE": "Finance",
    "HR": "HR",
    "PARENT": "Parent",
    "SCHOOL_COORDINATOR": "School coordinator",
    "SPOT": "Spot",
    "NO_ROLE": "No role",
}

_DATE_ERROR = "Looks like we still need a valid date range before we can show this report."


class ReportFilterError(ValueError):
    pass


def current_month_bounds(today: date | None = None) -> tuple[date, date]:
    day = today or today_ist()
    return day.replace(day=1), day


def age_in_days(created_at: datetime | None, today: date) -> int:
    aware = ensure_utc_aware(created_at)
    if aware is None:
        return 0
    opened = aware.astimezone(IST).date()
    return max(0, (today - opened).days)


def median_hours(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 1)


def count_roles(role_name_lists: list[list[str]]) -> dict[str, int]:
    """Count each ticket once per distinct role. People with two roles land in both."""
    counts: dict[str, int] = defaultdict(int)
    for names in role_name_lists:
        seen = set(names) or {"NO_ROLE"}
        for name in seen:
            counts[name] += 1
    return dict(counts)


def module_bucket(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in ("", "none", "null"):
        return "none"
    if raw in ("shadow", "shadow_support"):
        return "shadow_support"
    if raw in ("homecare", "home_care"):
        return "homecare"
    if raw == "b2b":
        return "b2b"
    return raw


def _parse_date(value: Optional[str], *, field: str) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError as exc:
        raise ReportFilterError(_DATE_ERROR) from exc


def _parse_status(value: Optional[str]) -> TicketStatus | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return TicketStatus(str(value).strip().upper())
    except ValueError as exc:
        raise ReportFilterError("Choose a status from the list.") from exc


def _parse_category(value: Optional[str]) -> TicketCategory | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return TicketCategory(str(value).strip().upper())
    except ValueError as exc:
        raise ReportFilterError("Choose a category from the list.") from exc


def _parse_module(value: Optional[str]) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    token = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if token in MODULE_ORDER or token in ("shadow", "home_care"):
        return module_bucket(token)
    if token.isascii() and token.replace("_", "").isalnum() and len(token) <= 64:
        return token
    raise ReportFilterError("Choose a product module from the list.")


def _parse_assignee(value: Optional[str]) -> int | None | str:
    """Return None (any), 'unassigned', or a user id."""
    if value is None or str(value).strip() == "":
        return None
    token = str(value).strip().lower()
    if token in ("unassigned", "none"):
        return "unassigned"
    try:
        user_id = int(token)
    except ValueError as exc:
        raise ReportFilterError("Choose an assignee from the list.") from exc
    if user_id <= 0:
        raise ReportFilterError("Choose an assignee from the list.")
    return user_id


def _resolve_dates(date_from: Optional[str], date_to: Optional[str]) -> tuple[date, date]:
    start = _parse_date(date_from, field="date_from")
    end = _parse_date(date_to, field="date_to")
    default_start, default_end = current_month_bounds()
    start = start or default_start
    end = end or default_end
    if start > end:
        raise ReportFilterError(_DATE_ERROR)
    if (end - start).days > _MAX_RANGE_DAYS:
        raise ReportFilterError("Choose a date range of 24 months or less.")
    return start, end


def _ist_window(start: date, end: date) -> tuple[datetime, datetime]:
    start_ist = datetime.combine(start, time.min, tzinfo=IST)
    end_exclusive = datetime.combine(end + timedelta(days=1), time.min, tzinfo=IST)
    return start_ist, end_exclusive


def _in_window(created_at: datetime | None, start_ist: datetime, end_exclusive: datetime) -> bool:
    aware = ensure_utc_aware(created_at)
    if aware is None:
        return False
    local = aware.astimezone(IST)
    return start_ist <= local < end_exclusive


def _share(count: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(round(100 * count / total))


def _chunks(ids: list[int], size: int = _ID_CHUNK):
    for index in range(0, len(ids), size):
        yield ids[index : index + size]


def _role_names(user: User | None) -> list[str]:
    if user is None:
        return []
    return list(user.role_names or [])


def _role_label(name: str) -> str:
    return ROLE_LABELS.get(name, name.replace("_", " ").title())


def _is_staff(role_names: list[str]) -> bool:
    return any(role != "PARENT" for role in role_names)


def _staff_name(user: User | None, role_names: list[str]) -> str | None:
    if user is None or not _is_staff(role_names):
        return None
    name = (user.full_name or "").strip()
    return name or f"Staff #{user.id}"


def _raiser_label(user: User | None, role_names: list[str]) -> str:
    staff = _staff_name(user, role_names)
    if staff:
        return staff
    if "PARENT" in role_names or not role_names:
        return "Parent" if "PARENT" in role_names else "No role"
    return ", ".join(_role_label(name) for name in role_names)


def _hours_between(start: datetime | None, end: datetime | None) -> float | None:
    start_at = ensure_utc_aware(start)
    end_at = ensure_utc_aware(end)
    if start_at is None or end_at is None:
        return None
    hours = (end_at - start_at).total_seconds() / 3600
    return max(0.0, hours)


def _load_users(db: Session, user_ids: set[int]) -> dict[int, User]:
    found: dict[int, User] = {}
    ids = [uid for uid in user_ids if uid]
    for chunk in _chunks(ids):
        rows = db.scalars(
            select(User).where(User.id.in_(chunk)).options(selectinload(User.roles))
        ).all()
        for user in rows:
            found[user.id] = user
    return found


def _load_case_codes(db: Session, case_ids: set[int]) -> dict[int, str]:
    found: dict[int, str] = {}
    ids = [cid for cid in case_ids if cid]
    for chunk in _chunks(ids):
        rows = db.execute(select(Case.id, Case.case_code).where(Case.id.in_(chunk))).all()
        for case_id, code in rows:
            found[int(case_id)] = code or ""
    return found


def _load_messages(db: Session, ticket_ids: list[int]) -> dict[int, list[tuple[int, datetime | None]]]:
    """Author and time only. Message text stays in the database."""
    grouped: dict[int, list[tuple[int, datetime | None]]] = defaultdict(list)
    for chunk in _chunks(ticket_ids):
        rows = db.execute(
            select(TicketMessage.ticket_id, TicketMessage.author_user_id, TicketMessage.created_at)
            .where(TicketMessage.ticket_id.in_(chunk))
            .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
        ).all()
        for ticket_id, author_id, created_at in rows:
            grouped[int(ticket_id)].append((int(author_id), created_at))
    return grouped


def _status_counts(tickets: list[SupportTicket]) -> list[dict[str, Any]]:
    total = len(tickets)
    by_status = {status: 0 for status in STATUS_ORDER}
    for ticket in tickets:
        by_status[ticket.status] = by_status.get(ticket.status, 0) + 1
    return [
        {
            "status": status.value,
            "label": STATUS_LABELS[status],
            "tickets": by_status[status],
            "share_pct": _share(by_status[status], total),
        }
        for status in STATUS_ORDER
    ]


def _category_rows(tickets: list[SupportTicket]) -> list[dict[str, Any]]:
    grid: dict[TicketCategory, dict[TicketStatus, int]] = {
        category: {status: 0 for status in STATUS_ORDER} for category in CATEGORY_ORDER
    }
    extras: dict[str, dict[str, int]] = {}
    for ticket in tickets:
        category = ticket.category if isinstance(ticket.category, TicketCategory) else TicketCategory(ticket.category)
        status = ticket.status if isinstance(ticket.status, TicketStatus) else TicketStatus(ticket.status)
        if category in grid:
            grid[category][status] += 1
        else:
            bucket = extras.setdefault(str(category), {s.value: 0 for s in STATUS_ORDER})
            bucket[status.value] += 1
    rows = []
    for category in CATEGORY_ORDER:
        counts = grid[category]
        total = sum(counts.values())
        still_open = counts[TicketStatus.OPEN] + counts[TicketStatus.IN_PROGRESS]
        rows.append(
            {
                "category": category.value,
                "label": CATEGORY_LABELS[category],
                "open": counts[TicketStatus.OPEN],
                "in_progress": counts[TicketStatus.IN_PROGRESS],
                "resolved": counts[TicketStatus.RESOLVED],
                "closed": counts[TicketStatus.CLOSED],
                "total": total,
                "still_open": still_open,
                "counts_only": category in RESTRICTED_CATEGORIES,
            }
        )
    for key in sorted(extras):
        counts = extras[key]
        total = sum(counts.values())
        still_open = counts[TicketStatus.OPEN.value] + counts[TicketStatus.IN_PROGRESS.value]
        rows.append(
            {
                "category": key,
                "label": key,
                "open": counts[TicketStatus.OPEN.value],
                "in_progress": counts[TicketStatus.IN_PROGRESS.value],
                "resolved": counts[TicketStatus.RESOLVED.value],
                "closed": counts[TicketStatus.CLOSED.value],
                "total": total,
                "still_open": still_open,
                "counts_only": False,
            }
        )
    return rows


def _module_rows(tickets: list[SupportTicket]) -> list[dict[str, Any]]:
    grid: dict[str, dict[TicketStatus, int]] = {
        key: {status: 0 for status in STATUS_ORDER} for key in MODULE_ORDER
    }
    for ticket in tickets:
        bucket = module_bucket(ticket.product_module)
        if bucket not in grid:
            grid[bucket] = {status: 0 for status in STATUS_ORDER}
        status = ticket.status if isinstance(ticket.status, TicketStatus) else TicketStatus(ticket.status)
        grid[bucket][status] += 1
    ordered = list(MODULE_ORDER) + sorted(key for key in grid if key not in MODULE_ORDER)
    rows = []
    for key in ordered:
        counts = grid[key]
        total = sum(counts.values())
        rows.append(
            {
                "module": key,
                "label": MODULE_LABELS.get(key, key.replace("_", " ").title()),
                "open": counts[TicketStatus.OPEN],
                "in_progress": counts[TicketStatus.IN_PROGRESS],
                "resolved": counts[TicketStatus.RESOLVED],
                "closed": counts[TicketStatus.CLOSED],
                "total": total,
                "still_open": counts[TicketStatus.OPEN] + counts[TicketStatus.IN_PROGRESS],
            }
        )
    return rows


def _apply_module_filter(stmt, product_module: str | None):
    if not product_module:
        return stmt
    if product_module == "none":
        return stmt.where(
            or_(
                SupportTicket.product_module.is_(None),
                func.trim(SupportTicket.product_module) == "",
            )
        )
    if product_module == "shadow_support":
        return stmt.where(func.lower(SupportTicket.product_module).in_(["shadow_support", "shadow"]))
    if product_module == "homecare":
        return stmt.where(func.lower(SupportTicket.product_module).in_(["homecare", "home_care", "home care"]))
    if product_module == "b2b":
        return stmt.where(func.lower(SupportTicket.product_module) == "b2b")
    return stmt.where(func.lower(SupportTicket.product_module) == product_module)


def build_support_ticket_report(
    db: Session,
    user: User,
    *,
    status: Optional[str] = None,
    category: Optional[str] = None,
    product_module: Optional[str] = None,
    assigned_to: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict[str, Any]:
    status_filter = _parse_status(status)
    category_filter = _parse_category(category)
    module_filter = _parse_module(product_module)
    assignee_filter = _parse_assignee(assigned_to)
    start, end = _resolve_dates(date_from, date_to)
    start_ist, end_exclusive = _ist_window(start, end)
    start_utc = start_ist.astimezone(timezone.utc)
    end_utc = end_exclusive.astimezone(timezone.utc)

    stmt = select(SupportTicket).where(
        SupportTicket.created_at >= start_utc,
        SupportTicket.created_at < end_utc,
    )
    visibility = staff_ticket_visibility_clause(db, user)
    if visibility is not None:
        stmt = stmt.where(visibility)
    if status_filter is not None:
        stmt = stmt.where(SupportTicket.status == status_filter)
    if category_filter is not None:
        stmt = stmt.where(SupportTicket.category == category_filter)
    stmt = _apply_module_filter(stmt, module_filter)
    stmt = stmt.order_by(SupportTicket.created_at.asc(), SupportTicket.id.asc())

    candidates = [ticket for ticket in db.scalars(stmt).all() if _in_window(ticket.created_at, start_ist, end_exclusive)]

    assignee_ids = {ticket.assigned_to_user_id for ticket in candidates if ticket.assigned_to_user_id}
    assignee_users = _load_users(db, assignee_ids)
    assignee_options = []
    for user_id in sorted(assignee_ids, key=lambda uid: ((assignee_users.get(uid).full_name or "").lower() if assignee_users.get(uid) else "", uid)):
        person = assignee_users.get(user_id)
        roles = _role_names(person)
        assignee_options.append(
            {
                "id": user_id,
                "name": _staff_name(person, roles) or _raiser_label(person, roles),
            }
        )
    unassigned_count = sum(1 for ticket in candidates if ticket.assigned_to_user_id is None)

    if assignee_filter == "unassigned":
        tickets = [ticket for ticket in candidates if ticket.assigned_to_user_id is None]
    elif isinstance(assignee_filter, int):
        tickets = [ticket for ticket in candidates if ticket.assigned_to_user_id == assignee_filter]
    else:
        tickets = candidates

    ticket_ids = [ticket.id for ticket in tickets]
    messages = _load_messages(db, ticket_ids)
    user_ids: set[int] = set(assignee_ids)
    for ticket in tickets:
        user_ids.add(ticket.raised_by_user_id)
        if ticket.assigned_to_user_id:
            user_ids.add(ticket.assigned_to_user_id)
        for author_id, _created in messages.get(ticket.id, []):
            user_ids.add(author_id)
    users = _load_users(db, user_ids)
    users.update(assignee_users)
    case_codes = _load_case_codes(db, {ticket.case_id for ticket in tickets if ticket.case_id})

    today = today_ist()
    reply_rows: dict[int, dict[str, Any]] = {}
    first_reply_hours: dict[TicketCategory, list[float]] = defaultdict(list)
    question_counts = {key: {"total": 0, "still_open": 0} for key, _label in QUESTION_GROUPS}
    open_no_reply = {"within_7": 0, "8_to_30": 0, "over_30": 0}
    in_progress_ages = {"within_7": 0, "8_to_30": 0, "over_30": 0}
    oldest_open: int | None = None
    oldest_in_progress: int | None = None
    queue: list[dict[str, Any]] = []
    restricted_omitted = 0

    for ticket in tickets:
        raiser_roles = _role_names(users.get(ticket.raised_by_user_id))
        thread = messages.get(ticket.id, [])
        others = [(author_id, created) for author_id, created in thread if author_id != ticket.raised_by_user_id]
        others.sort(key=lambda item: (ensure_utc_aware(item[1]) or datetime.max.replace(tzinfo=timezone.utc), item[0]))
        first_other = others[0] if others else None
        if first_other is not None:
            hours = _hours_between(ticket.created_at, first_other[1])
            if hours is not None:
                category = ticket.category if isinstance(ticket.category, TicketCategory) else TicketCategory(ticket.category)
                first_reply_hours[category].append(hours)

        staff_replies = []
        for author_id, created in others:
            author = users.get(author_id)
            author_roles = _role_names(author)
            if not _is_staff(author_roles):
                continue
            staff_replies.append((author_id, created, author, author_roles))
        staff_replies.sort(key=lambda item: (ensure_utc_aware(item[1]) or datetime.max.replace(tzinfo=timezone.utc), item[0]))
        seen_authors: set[int] = set()
        for author_id, _created, author, author_roles in staff_replies:
            seen_authors.add(author_id)
            row = reply_rows.get(author_id)
            if row is None:
                row = {
                    "user_id": author_id,
                    "name": _staff_name(author, author_roles) or "Staff",
                    "roles": [_role_label(name) for name in author_roles if name != "PARENT"] or ["Staff"],
                    "replies": 0,
                    "tickets": 0,
                    "first_replies": 0,
                }
                reply_rows[author_id] = row
            row["replies"] += 1
        first_staff_id = staff_replies[0][0] if staff_replies else None
        for author_id in seen_authors:
            reply_rows[author_id]["tickets"] += 1
            if author_id == first_staff_id:
                reply_rows[author_id]["first_replies"] += 1

        group = classify_question(ticket.subject, ticket.body)
        if group not in question_counts:
            group = "other"
        question_counts[group]["total"] += 1
        still_open = ticket.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS)
        if still_open:
            question_counts[group]["still_open"] += 1

        age = age_in_days(ticket.created_at, today)
        if ticket.status == TicketStatus.OPEN:
            oldest_open = age if oldest_open is None else max(oldest_open, age)
            if first_other is None:
                if age <= 7:
                    open_no_reply["within_7"] += 1
                elif age <= 30:
                    open_no_reply["8_to_30"] += 1
                else:
                    open_no_reply["over_30"] += 1
        elif ticket.status == TicketStatus.IN_PROGRESS:
            oldest_in_progress = age if oldest_in_progress is None else max(oldest_in_progress, age)
            if age <= 7:
                in_progress_ages["within_7"] += 1
            elif age <= 30:
                in_progress_ages["8_to_30"] += 1
            else:
                in_progress_ages["over_30"] += 1

        category = ticket.category if isinstance(ticket.category, TicketCategory) else TicketCategory(ticket.category)
        if category in RESTRICTED_CATEGORIES:
            if ticket.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS):
                restricted_omitted += 1
            continue
        if ticket.status not in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS):
            continue
        assignee = users.get(ticket.assigned_to_user_id) if ticket.assigned_to_user_id else None
        assignee_roles = _role_names(assignee)
        queue.append(
            {
                "id": ticket.id,
                "status": ticket.status.value,
                "status_label": STATUS_LABELS[ticket.status],
                "category": category.value,
                "category_label": CATEGORY_LABELS.get(category, category.value),
                "module": module_bucket(ticket.product_module),
                "module_label": MODULE_LABELS.get(module_bucket(ticket.product_module), module_bucket(ticket.product_module)),
                "case_code": case_codes.get(ticket.case_id) if ticket.case_id else None,
                "raised_by": _raiser_label(users.get(ticket.raised_by_user_id), raiser_roles),
                "raised_by_roles": [_role_label(name) for name in (raiser_roles or ["NO_ROLE"])],
                "assignee": _staff_name(assignee, assignee_roles) or ("Unassigned" if assignee is None else _raiser_label(assignee, assignee_roles)),
                "opened_on": ensure_utc_aware(ticket.created_at).astimezone(IST).date().isoformat()
                if ensure_utc_aware(ticket.created_at)
                else None,
                "age_days": age,
                "awaiting_first_reply": first_other is None,
            }
        )

    queue.sort(key=lambda row: (0 if row["status"] == TicketStatus.OPEN.value else 1, -row["age_days"], row["id"]))
    queue_total = len(queue)
    queue_rows = queue[:QUEUE_ROW_LIMIT]

    role_lists = [_role_names(users.get(ticket.raised_by_user_id)) for ticket in tickets]
    raised_counts = count_roles(role_lists)
    raised_by_role = [
        {"role": role, "label": _role_label(role), "tickets": count}
        for role, count in sorted(raised_counts.items(), key=lambda item: (-item[1], _role_label(item[0])))
    ]

    staff_replies = sorted(
        reply_rows.values(),
        key=lambda row: (-row["replies"], row["name"].lower(), row["user_id"]),
    )
    for row in staff_replies:
        row.pop("user_id", None)

    by_status = {row["status"]: row["tickets"] for row in _status_counts(tickets)}
    open_waiting = sum(open_no_reply.values())
    in_progress_total = by_status.get(TicketStatus.IN_PROGRESS.value, 0)

    filters = {
        "status": status_filter.value if status_filter else None,
        "category": category_filter.value if category_filter else None,
        "product_module": module_filter,
        "assigned_to": "unassigned" if assignee_filter == "unassigned" else assignee_filter,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "timezone": "Asia/Kolkata",
    }

    return {
        "read_only": True,
        "timezone": "Asia/Kolkata",
        "filters": filters,
        "total": len(tickets),
        "by_status": _status_counts(tickets),
        "in_flight": by_status.get(TicketStatus.OPEN.value, 0) + in_progress_total,
        "by_category": _category_rows(tickets),
        "by_module": _module_rows(tickets),
        "raised_by_role": raised_by_role,
        "staff_replies": staff_replies,
        "first_reply_hours": [
            {
                "category": category.value,
                "label": CATEGORY_LABELS[category],
                "median_hours": median_hours(first_reply_hours.get(category, [])),
                "tickets_with_reply": len(first_reply_hours.get(category, [])),
            }
            for category in CATEGORY_ORDER
        ],
        "aging": {
            "open_no_reply": open_waiting,
            "open_no_reply_within_7_days": open_no_reply["within_7"],
            "open_no_reply_8_to_30_days": open_no_reply["8_to_30"],
            "open_no_reply_older_than_30_days": open_no_reply["over_30"],
            "oldest_open_days": oldest_open,
            "in_progress": in_progress_total,
            "in_progress_within_7_days": in_progress_ages["within_7"],
            "in_progress_8_to_30_days": in_progress_ages["8_to_30"],
            "in_progress_older_than_7_days": in_progress_ages["8_to_30"] + in_progress_ages["over_30"],
            "in_progress_older_than_30_days": in_progress_ages["over_30"],
            "oldest_in_progress_days": oldest_in_progress,
        },
        "question_groups": [
            {
                "key": key,
                "label": label,
                "total": question_counts[key]["total"],
                "still_open": question_counts[key]["still_open"],
            }
            for key, label in QUESTION_GROUPS
        ],
        "queue": queue_rows,
        "queue_total": queue_total,
        "queue_truncated": queue_total > len(queue_rows),
        "restricted_omitted": restricted_omitted,
        "assignee_options": assignee_options,
        "unassigned_count": unassigned_count,
        "notes": [
            "Read-only. This report does not reply, close, resolve, or change a ticket.",
            "Dates are the day the ticket was opened, in Asia/Kolkata.",
            "A person with more than one role is counted in each role.",
            "Median hours run until the first reply from someone other than the person who raised the ticket.",
            "Question groups come from words in the subject and the opening message. One ticket, one group.",
            "POSH and CPP are counts only. They are left out of the queue, and this report does not suggest a reply.",
        ],
    }


def report_to_xlsx(payload: dict[str, Any], user: User) -> bytes:
    filters = payload.get("filters") or {}
    subtitle = (
        f"Opened {filters.get('date_from')} to {filters.get('date_to')} (Asia/Kolkata). "
        "Read-only. No ticket was changed."
    )
    status_rows = [
        {"Status": row["label"], "Tickets": row["tickets"], "Share": f"{row['share_pct']}%"}
        for row in payload.get("by_status") or []
    ]
    queue_rows = [
        {
            "Ticket": row["id"],
            "Status": row["status_label"],
            "Category": row["category_label"],
            "Module": row["module_label"],
            "Case code": row.get("case_code") or "",
            "Raised by": row["raised_by"],
            "Raised by role": ", ".join(row.get("raised_by_roles") or []),
            "Assignee": row["assignee"],
            "Opened": row.get("opened_on") or "",
            "Age (days)": row["age_days"],
            "Awaiting first reply": "Yes" if row["awaiting_first_reply"] else "No",
        }
        for row in payload.get("queue") or []
    ]
    category_rows = [
        {
            "Category": row["label"],
            "Open": row["open"],
            "In progress": row["in_progress"],
            "Resolved": row["resolved"],
            "Closed": row["closed"],
            "Total": row["total"],
            "Still open": row["still_open"],
        }
        for row in payload.get("by_category") or []
    ]
    module_rows = [
        {
            "Module": row["label"],
            "Open": row["open"],
            "In progress": row["in_progress"],
            "Resolved": row["resolved"],
            "Closed": row["closed"],
            "Total": row["total"],
            "Still open": row["still_open"],
        }
        for row in payload.get("by_module") or []
    ]
    role_rows = [
        {"Role": row["label"], "Tickets": row["tickets"]}
        for row in payload.get("raised_by_role") or []
    ]
    reply_rows = [
        {
            "Name": row["name"],
            "Roles": ", ".join(row.get("roles") or []),
            "Replies": row["replies"],
            "Tickets": row["tickets"],
            "First replies": row["first_replies"],
        }
        for row in payload.get("staff_replies") or []
    ]
    hours_rows = [
        {
            "Category": row["label"],
            "Median hours": "" if row["median_hours"] is None else row["median_hours"],
            "Tickets with a reply": row["tickets_with_reply"],
        }
        for row in payload.get("first_reply_hours") or []
    ]
    aging = payload.get("aging") or {}
    aging_rows = [
        {"Metric": "Open with no reply yet", "Count": aging.get("open_no_reply", 0)},
        {"Metric": "Open, no reply, 7 days or newer", "Count": aging.get("open_no_reply_within_7_days", 0)},
        {"Metric": "Open, no reply, 8 to 30 days", "Count": aging.get("open_no_reply_8_to_30_days", 0)},
        {"Metric": "Open, no reply, older than 30 days", "Count": aging.get("open_no_reply_older_than_30_days", 0)},
        {"Metric": "Oldest open ticket (days)", "Count": "" if aging.get("oldest_open_days") is None else aging.get("oldest_open_days")},
        {"Metric": "In progress", "Count": aging.get("in_progress", 0)},
        {"Metric": "In progress, 7 days or newer", "Count": aging.get("in_progress_within_7_days", 0)},
        {"Metric": "In progress, 8 to 30 days", "Count": aging.get("in_progress_8_to_30_days", 0)},
        {"Metric": "In progress, older than 7 days", "Count": aging.get("in_progress_older_than_7_days", 0)},
        {"Metric": "In progress, older than 30 days", "Count": aging.get("in_progress_older_than_30_days", 0)},
        {
            "Metric": "Oldest in-progress ticket (days)",
            "Count": "" if aging.get("oldest_in_progress_days") is None else aging.get("oldest_in_progress_days"),
        },
        {"Metric": "Open and in progress", "Count": payload.get("in_flight", 0)},
    ]
    group_rows = [
        {"Type": row["label"], "All": row["total"], "Still open": row["still_open"]}
        for row in payload.get("question_groups") or []
    ]
    if not queue_rows:
        queue_rows = [
            {
                "Ticket": "No open or in-progress tickets for these filters.",
                "Status": "",
                "Category": "",
                "Module": "",
                "Case code": "",
                "Raised by": "",
                "Raised by role": "",
                "Assignee": "",
                "Opened": "",
                "Age (days)": "",
                "Awaiting first reply": "",
            }
        ]
    if payload.get("queue_truncated"):
        queue_rows.append(
            {
                "Ticket": "",
                "Status": "",
                "Category": "",
                "Module": "",
                "Case code": "",
                "Raised by": "",
                "Raised by role": "",
                "Assignee": "",
                "Opened": "",
                "Age (days)": "",
                "Awaiting first reply": f"Showing {len(payload.get('queue') or [])} of {payload.get('queue_total')}",
            }
        )
    sheets = {
        "Status": status_rows,
        "Live queue": queue_rows,
        "By category": category_rows,
        "By module": module_rows,
        "Raised by role": role_rows or [{"Role": "No rows for the selected filters", "Tickets": ""}],
        "Staff replies": reply_rows or [{"Name": "No rows for the selected filters", "Roles": "", "Replies": "", "Tickets": "", "First replies": ""}],
        "First reply hours": hours_rows,
        "Aging": aging_rows,
        "Question groups": group_rows,
    }
    return payload_to_xlsx(
        title="Support tickets report",
        subtitle=subtitle,
        user=user,
        rows=status_rows,
        sheets=sheets,
    )
