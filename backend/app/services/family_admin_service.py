from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.parent import ParentGuardian, parent_child_link
from app.models.user import InviteToken, User
from app.services import auth_service, email_service
from app.services.user_provision_service import login_ready


def _parent_invite_metadata(*, full_name: str, phone: str | None, extra: dict | None = None) -> dict:
    meta = {
        "full_name": full_name.strip(),
        "phone": (phone or "").strip() or None,
    }
    if extra:
        meta.update(extra)
    return meta


def provision_parent_for_child(
    db: Session,
    *,
    email: str,
    full_name: str,
    phone: str | None,
    child: Child,
    password: str | None = None,
) -> tuple[User, ParentGuardian]:
    """Ensure a PARENT user exists and is linked to the child."""
    from app.core.permissions import RoleName

    email_l = email.lower().strip()
    user = db.scalars(select(User).where(User.email == email_l)).first()
    if user:
        if RoleName.PARENT.value not in user.role_names:
            primary = user.role_names[0].replace("_", " ").title() if user.role_names else "another role"
            raise ValueError(f"User already present as {primary}.")
        pg = db.scalars(
            select(ParentGuardian)
            .where(ParentGuardian.user_id == user.id)
            .options(selectinload(ParentGuardian.children))
        ).first()
        if not pg:
            pg = ParentGuardian(user_id=user.id)
            db.add(pg)
            db.flush()
        assert_no_duplicate_child_for_parent(
            pg,
            first_name=child.first_name,
            last_name=child.last_name,
            date_of_birth=child.date_of_birth,
        )
        if child not in pg.children:
            pg.children.append(child)
        if full_name.strip() and not (user.full_name or "").strip():
            user.full_name = full_name.strip()
        if phone and not user.phone:
            user.phone = phone.strip()
        db.flush()
        return user, pg

    pwd = password or secrets.token_urlsafe(24)
    user = auth_service.create_user(
        db,
        email=email_l,
        password=pwd,
        full_name=full_name.strip(),
        role_names=[RoleName.PARENT.value],
    )
    if phone:
        user.phone = phone.strip()
    pg = ParentGuardian(user_id=user.id)
    db.add(pg)
    db.flush()
    pg.children.append(child)
    db.flush()
    return user, pg


def rotate_invite_token(
    db: Session,
    invite: InviteToken,
    *,
    created_by_user_id: int,
) -> InviteToken:
    """Retire an unused invite and mint a fresh token with the same metadata."""
    now = datetime.now(timezone.utc)
    prior_meta = dict(invite.invite_metadata or {})
    invite.used_at = now
    consumed = dict(prior_meta)
    consumed["consumed_reason"] = "rotated"
    invite.invite_metadata = consumed
    new_invite = InviteToken(
        email=invite.email,
        role_name=invite.role_name,
        module_assignments=list(invite.module_assignments or []),
        token=secrets.token_urlsafe(32),
        expires_at=now + timedelta(days=7),
        created_by_user_id=created_by_user_id,
        linked_child_id=invite.linked_child_id,
        invite_metadata=prior_meta,
    )
    db.add(new_invite)
    db.flush()
    return new_invite


def parent_has_portal_session(db: Session, user_id: int) -> bool:
    from app.services.parent_service import parent_has_portal_session as _has_session

    return _has_session(db, user_id)


def refresh_parent_portal_invite(
    db: Session,
    parent_user_id: int,
    created_by_user_id: int,
    *,
    child_id: int | None = None,
    send_email: bool = True,
    background_tasks=None,
    force_resend: bool = False,
) -> str:
    """Consume stale parent invites and issue a fresh portal invite link."""
    from app.core.permissions import RoleName

    user = db.get(User, parent_user_id)
    if not user or RoleName.PARENT.value not in user.role_names:
        raise ValueError("Parent user not found")
    consume_pending_parent_invites(db, user.email, reason="rotated")
    return issue_parent_invite(
        db,
        parent_user_id,
        created_by_user_id,
        child_id=child_id,
        send_email=send_email,
        background_tasks=background_tasks,
        force_resend=force_resend,
    )


def list_parents_awaiting_first_login(db: Session) -> dict:
    """Parents linked to open cases who have never signed in or accepted an invite."""
    from app.core.permissions import RoleName
    from app.core.timezone import ensure_utc_aware

    now = datetime.now(timezone.utc)
    closed_val = CaseStatus.CLOSED.value

    cases_by_child: dict[int, list[Case]] = {}
    for case in db.scalars(select(Case)).all():
        cases_by_child.setdefault(case.child_id, []).append(case)

    def child_has_open_case(child_id: int) -> bool:
        rows = cases_by_child.get(child_id, [])
        return any((c.status.value if c.status else None) != closed_val for c in rows)

    parent_rows = db.scalars(
        select(ParentGuardian).options(
            selectinload(ParentGuardian.children),
            selectinload(ParentGuardian.user),
        )
    ).all()

    seen_user_ids: set[int] = set()
    items: list[dict] = []

    for pg in parent_rows:
        u = pg.user
        if not u or not u.is_active or RoleName.PARENT.value not in u.role_names:
            continue
        if u.id in seen_user_ids or parent_has_portal_session(db, u.id):
            continue
        open_children = [c for c in pg.children if child_has_open_case(c.id)]
        if not open_children:
            continue
        child = open_children[0]
        seen_user_ids.add(u.id)
        items.append(
            {
                "userId": u.id,
                "parentEmail": u.email,
                "parentName": u.full_name,
                "childId": child.id,
                "childName": child.full_name,
                "loginReady": login_ready(u, db),
                "kind": "parent_user",
            }
        )

    pending_by_child: dict[int, InviteToken] = {}
    for inv in db.scalars(
        select(InviteToken)
        .where(
            InviteToken.used_at.is_(None),
            InviteToken.linked_child_id.isnot(None),
            InviteToken.role_name == "PARENT",
        )
        .order_by(InviteToken.id.desc())
    ).all():
        cid = inv.linked_child_id
        if cid and cid not in pending_by_child:
            pending_by_child[cid] = inv

    child_has_parent_user: dict[int, bool] = {}
    for pg in parent_rows:
        for c in pg.children:
            child_has_parent_user[c.id] = True

    for child_id, inv in pending_by_child.items():
        if not child_has_open_case(child_id):
            continue
        existing_user = db.scalars(select(User).where(User.email == inv.email.lower())).first()
        if existing_user and existing_user.id in seen_user_ids:
            continue
        if existing_user and parent_has_portal_session(db, existing_user.id):
            continue
        if child_has_parent_user.get(child_id) and existing_user:
            continue
        child = db.get(Child, child_id)
        expired = ensure_utc_aware(inv.expires_at) <= now
        items.append(
            {
                "userId": existing_user.id if existing_user else None,
                "parentEmail": inv.email,
                "parentName": (inv.invite_metadata or {}).get("full_name") or inv.email,
                "childId": child_id,
                "childName": child.full_name if child else None,
                "inviteId": inv.id,
                "inviteExpired": expired,
                "kind": "invite_only",
            }
        )

    return {"count": len(items), "items": items}


def bulk_invite_parents_awaiting_first_login(
    db: Session,
    *,
    actor_user_id: int,
    background_tasks,
    user_ids: list[int] | None = None,
    invite_ids: list[int] | None = None,
) -> dict:
    """Send fresh portal invites to parents who have never logged in."""
    from app.services.email.delivery_metadata import delivery_metadata_for_email
    from app.services.email.service import enqueue_password_reset_email, invite_email_delivery_status
    from app.services import password_reset_service

    roster = list_parents_awaiting_first_login(db)
    targets = roster["items"]
    if user_ids is not None:
        allowed = set(user_ids)
        targets = [t for t in targets if t.get("userId") in allowed]
    if invite_ids is not None:
        allowed_inv = set(invite_ids)
        targets = [t for t in targets if t.get("inviteId") in allowed_inv]

    sent = 0
    skipped = 0
    errors: list[dict] = []
    delivery = invite_email_delivery_status(send_email=True, background_tasks=background_tasks)

    for row in targets:
        email = row["parentEmail"]
        meta = delivery_metadata_for_email(db, email, None)
        if meta.get("is_email_suppressed"):
            skipped += 1
            errors.append({"email": email, "error": "email_suppressed"})
            continue
        try:
            if row.get("userId"):
                user = db.get(User, row["userId"])
                if not user:
                    skipped += 1
                    errors.append({"email": email, "error": "user_missing"})
                    continue
                if login_ready(user, db):
                    plain, token_id = password_reset_service.get_or_create_reset_token(
                        db, user, force_new=True
                    )
                    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password/{plain}"
                    if background_tasks is not None and delivery != "skipped_no_smtp":
                        enqueue_password_reset_email(
                            background_tasks,
                            db,
                            to=user.email,
                            full_name=user.full_name or user.email,
                            reset_url=reset_url,
                            expires_hours=settings.password_reset_expire_hours,
                            entity_id=token_id,
                            force_resend=True,
                        )
                    sent += 1
                else:
                    refresh_parent_portal_invite(
                        db,
                        row["userId"],
                        actor_user_id,
                        child_id=row.get("childId"),
                        send_email=True,
                        background_tasks=background_tasks,
                        force_resend=True,
                    )
                    sent += 1
            elif row.get("inviteId"):
                inv = db.get(InviteToken, row["inviteId"])
                if not inv or inv.used_at is not None:
                    skipped += 1
                    errors.append({"email": email, "error": "invite_missing"})
                    continue
                new_inv = rotate_invite_token(db, inv, created_by_user_id=actor_user_id)
                url = f"{settings.frontend_url.rstrip('/')}/invite/{new_inv.token}"
                child_name = row.get("childName") or "your child"
                display_name = row.get("parentName") or email
                if background_tasks is not None:
                    queue_parent_portal_invite_email(
                        background_tasks,
                        db,
                        to=email,
                        invite_url=url,
                        full_name=display_name,
                        child_name=child_name,
                        invite_id=new_inv.id,
                        force_resend=True,
                    )
                else:
                    _send_parent_invite_email(email, url, display_name, child_name)
                sent += 1
            else:
                skipped += 1
                errors.append({"email": email, "error": "no_target"})
        except Exception as exc:
            skipped += 1
            errors.append({"email": email, "error": str(exc)[:200]})

    return {"sent": sent, "skipped": skipped, "errors": errors, "total": len(targets)}


def consume_pending_parent_invites(db: Session, email: str, *, reason: str = "activated") -> None:
    """Mark unused parent portal invites consumed (e.g. after admin set-password)."""
    from app.core.timezone import ensure_utc_aware

    now = datetime.now(timezone.utc)
    email_l = email.lower().strip()
    rows = db.scalars(
        select(InviteToken).where(
            InviteToken.email == email_l,
            InviteToken.used_at.is_(None),
            InviteToken.role_name == "PARENT",
        )
    ).all()
    for inv in rows:
        inv.used_at = now
        meta = dict(inv.invite_metadata or {})
        meta["consumed_reason"] = reason
        inv.invite_metadata = meta
    db.flush()


def backfill_parent_from_invite(db: Session, invite: InviteToken) -> User | None:
    """Create parent user + child link for legacy invites that predate upfront provisioning."""
    from app.core.permissions import RoleName

    if not invite.linked_child_id or invite.used_at is not None:
        return None
    email_l = invite.email.lower().strip()
    existing = db.scalars(select(User).where(User.email == email_l)).first()
    if existing:
        return existing
    child = db.get(Child, invite.linked_child_id)
    if not child:
        return None
    meta = invite.invite_metadata or {}
    full_name = (meta.get("full_name") or meta.get("client_name") or email_l.split("@")[0]).strip()
    phone = meta.get("phone") or meta.get("client_phone")
    user, _pg = provision_parent_for_child(
        db,
        email=email_l,
        full_name=full_name,
        phone=phone,
        child=child,
        password=secrets.token_urlsafe(24),
    )
    if RoleName.PARENT.value not in user.role_names:
        return user
    return user


def _build_family_row(
    child: Child,
    *,
    parents: list[dict],
    child_cases: list[dict],
    pending: dict | None,
) -> dict:
    label = child.full_name
    case_codes = [c["caseCode"] for c in child_cases if c.get("caseCode")]
    has_cases = len(child_cases) > 0
    closed_val = CaseStatus.CLOSED.value
    all_cases_closed = has_cases and all(c.get("status") == closed_val for c in child_cases)
    has_open_case = any(c.get("status") != closed_val for c in child_cases)
    primary_case_id = None
    for c in child_cases:
        if c.get("status") != closed_val:
            primary_case_id = c["caseId"]
            break
    if primary_case_id is None and child_cases:
        primary_case_id = child_cases[0]["caseId"]
    return {
        "childId": child.id,
        "childName": label,
        "firstName": child.first_name,
        "lastName": child.last_name,
        "dateOfBirth": child.date_of_birth.isoformat() if child.date_of_birth else None,
        "parents": parents,
        "cases": child_cases,
        "caseCodes": case_codes,
        "allCasesClosed": all_cases_closed,
        "hasOpenCase": has_open_case,
        "primaryCaseId": primary_case_id,
        "hasParent": bool(parents),
        "pendingInvite": pending,
    }


def _family_support_maps(
    db: Session,
    *,
    child_ids: list[int] | None = None,
) -> tuple[dict[int, list[dict]], dict[int, list[dict]], dict[int, dict]]:
    """Parents, cases, and pending invites keyed by child id."""
    child_id_set = set(child_ids) if child_ids else None
    parent_stmt = select(ParentGuardian).options(
        selectinload(ParentGuardian.children),
        selectinload(ParentGuardian.user),
    )
    parent_rows = db.scalars(parent_stmt).all()
    if child_id_set is not None:
        parent_rows = [
            pg
            for pg in parent_rows
            if any(c.id in child_id_set for c in (pg.children or []))
        ]
    parent_users = [pg.user for pg in parent_rows if pg.user]
    portal_session_ids = set()
    if parent_users:
        from app.services.user_provision_service import _parent_portal_session_user_ids

        portal_session_ids = _parent_portal_session_user_ids(
            db, [u.id for u in parent_users if u.is_active]
        )
    pending_by_email = {}
    if parent_users:
        from app.services.user_provision_service import _pending_invites_by_email

        pending_by_email = _pending_invites_by_email(db, [u.email for u in parent_users])

    child_parents: dict[int, list[dict]] = {}
    for pg in parent_rows:
        u = pg.user
        if not u:
            continue
        email_key = u.email.lower().strip()
        login_ready_flag = bool(
            u.is_active
            and u.password_hash
            and pending_by_email.get(email_key) is None
            and (u.id in portal_session_ids or "PARENT" not in (u.role_names or []))
        )
        info = {
            "parentId": pg.id,
            "userId": u.id,
            "parentName": u.full_name,
            "parentEmail": u.email,
            "parentPhone": u.phone,
            "parentIsActive": bool(u.is_active),
            "parentLoginReady": login_ready_flag,
        }
        seen_child: set[int] = set()
        for c in pg.children:
            if child_id_set is not None and c.id not in child_id_set:
                continue
            if c.id in seen_child:
                continue
            seen_child.add(c.id)
            parents = child_parents.setdefault(c.id, [])
            if not any(p["userId"] == u.id for p in parents):
                parents.append(info)

    cases_by_child: dict[int, list[dict]] = {}
    case_stmt = select(Case).order_by(Case.id.desc())
    if child_id_set is not None:
        case_stmt = case_stmt.where(Case.child_id.in_(child_id_set))
    for case in db.scalars(case_stmt).all():
        status_val = case.status.value if case.status else None
        cases_by_child.setdefault(case.child_id, []).append(
            {
                "caseId": case.id,
                "caseCode": case.case_code,
                "status": status_val,
                "caseManagerUserId": case.case_manager_user_id,
            }
        )

    now = datetime.now(timezone.utc)
    pending_by_child: dict[int, dict] = {}
    for inv in db.scalars(
        select(InviteToken)
        .where(
            InviteToken.used_at.is_(None),
            InviteToken.linked_child_id.isnot(None),
            InviteToken.role_name == "PARENT",
        )
        .order_by(InviteToken.id.desc())
    ).all():
        if inv.linked_child_id and inv.linked_child_id not in pending_by_child:
            if child_id_set is not None and inv.linked_child_id not in child_id_set:
                continue
            from app.core.timezone import ensure_utc_aware

            expired = ensure_utc_aware(inv.expires_at) <= now
            pending_entry = {
                "pendingEmail": inv.email,
                "inviteId": inv.id,
                "inviteExpiresAt": inv.expires_at.isoformat() if inv.expires_at else None,
                "isExpired": expired,
            }
            if not expired:
                pending_entry["inviteUrl"] = (
                    f"{settings.frontend_url.rstrip('/')}/invite/{inv.token}"
                )
            pending_by_child[inv.linked_child_id] = pending_entry

    return child_parents, cases_by_child, pending_by_child


def _family_child_search_stmt(search: str | None):
    from app.models.user import User

    q = (search or "").strip().lower()
    stmt = select(Child.id).distinct()
    if not q:
        return stmt.order_by(Child.first_name.asc(), Child.last_name.asc(), Child.id.asc())
    pattern = f"%{q}%"
    stmt = (
        stmt.outerjoin(parent_child_link, parent_child_link.c.child_id == Child.id)
        .outerjoin(ParentGuardian, ParentGuardian.id == parent_child_link.c.parent_guardian_id)
        .outerjoin(User, User.id == ParentGuardian.user_id)
        .outerjoin(Case, Case.child_id == Child.id)
        .where(
            or_(
                func.lower(Child.first_name).like(pattern),
                func.lower(Child.last_name).like(pattern),
                func.lower(func.concat(Child.first_name, " ", Child.last_name)).like(pattern),
                func.lower(User.email).like(pattern),
                func.lower(User.full_name).like(pattern),
                func.lower(Case.case_code).like(pattern),
            )
        )
    )
    return stmt.order_by(Child.first_name.asc(), Child.last_name.asc(), Child.id.asc())


def list_families_paginated(
    db: Session,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 15,
) -> dict:
    from app.core.pagination import paginate_query, paginated_response

    id_stmt = _family_child_search_stmt(search)
    id_rows, total = paginate_query(db, id_stmt, page=page, page_size=page_size)
    child_ids = [int(row[0] if isinstance(row, tuple) else row) for row in id_rows]
    if not child_ids:
        return paginated_response([], total, page, page_size)

    children = list(
        db.scalars(
            select(Child)
            .where(Child.id.in_(child_ids))
            .order_by(Child.first_name.asc(), Child.last_name.asc(), Child.id.asc())
        ).all()
    )
    child_parents, cases_by_child, pending_by_child = _family_support_maps(db, child_ids=child_ids)
    items = [
        _build_family_row(
            child,
            parents=child_parents.get(child.id, []),
            child_cases=cases_by_child.get(child.id, []),
            pending=pending_by_child.get(child.id),
        )
        for child in children
    ]
    return paginated_response(items, total, page, page_size)


def list_families(db: Session, search: str | None = None) -> list[dict]:
    child_parents, cases_by_child, pending_by_child = _family_support_maps(db)
    children = db.scalars(select(Child).order_by(Child.first_name, Child.last_name)).all()
    q = (search or "").strip().lower()
    result = []
    for child in children:
        parents = child_parents.get(child.id, [])
        child_cases = cases_by_child.get(child.id, [])
        case_codes = [c["caseCode"] for c in child_cases if c.get("caseCode")]
        if q:
            hay = f"{child.full_name} {' '.join(p['parentEmail'] for p in parents)} {' '.join(case_codes)}".lower()
            if q not in hay:
                continue
        result.append(
            _build_family_row(
                child,
                parents=parents,
                child_cases=child_cases,
                pending=pending_by_child.get(child.id),
            )
        )
    return result


def _child_identity_key(first_name: str, last_name: str, date_of_birth) -> tuple[str, str, object]:
    return (first_name.strip().lower(), last_name.strip().lower(), date_of_birth)


def find_duplicate_child_for_parent(
    pg: ParentGuardian,
    *,
    first_name: str,
    last_name: str,
    date_of_birth=None,
) -> Child | None:
    """Return an existing child on this parent with the same name and date of birth."""
    target = _child_identity_key(first_name, last_name, date_of_birth)
    for child in pg.children:
        if _child_identity_key(child.first_name, child.last_name, child.date_of_birth) == target:
            return child
    return None


def assert_no_duplicate_child_for_parent(
    pg: ParentGuardian,
    *,
    first_name: str,
    last_name: str,
    date_of_birth=None,
) -> None:
    duplicate = find_duplicate_child_for_parent(
        pg,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
    )
    if duplicate:
        raise ValueError(
            f"This parent already has a child profile for {duplicate.full_name}"
            f" (child id {duplicate.id}). Use the existing record or add a different child."
        )


def create_child(db: Session, first_name: str, last_name: str, date_of_birth=None) -> Child:
    child = Child(first_name=first_name.strip(), last_name=last_name.strip(), date_of_birth=date_of_birth)
    db.add(child)
    db.flush()
    return child


def create_family(
    db: Session,
    *,
    parent_email: str,
    parent_full_name: str,
    parent_phone: str | None,
    child_first: str,
    child_last: str,
    child_dob=None,
    send_invite: bool,
    password: str | None,
    created_by_user_id: int,
) -> dict:
    from app.core.permissions import RoleName
    from app.services.invite_policy_service import assert_can_create_invite

    email = parent_email.lower().strip()
    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing:
        if RoleName.PARENT.value not in existing.role_names:
            primary = existing.role_names[0].replace("_", " ").title() if existing.role_names else "another role"
            raise ValueError(f"User already present as {primary}.")
        pg = db.scalars(
            select(ParentGuardian)
            .where(ParentGuardian.user_id == existing.id)
            .options(selectinload(ParentGuardian.children))
        ).first()
        if not pg:
            pg = ParentGuardian(user_id=existing.id)
            db.add(pg)
            db.flush()
        assert_no_duplicate_child_for_parent(
            pg,
            first_name=child_first,
            last_name=child_last,
            date_of_birth=child_dob,
        )
        child = create_child(db, child_first, child_last, child_dob)
        if child not in pg.children:
            pg.children.append(child)
        db.flush()
        return {
            "childId": child.id,
            "parentUserId": existing.id,
            "inviteUrl": None,
            "linkedExistingParent": True,
        }

    child = create_child(db, child_first, child_last, child_dob)

    if send_invite:
        assert_can_create_invite(db, email, RoleName.PARENT.value)
        user, _pg = provision_parent_for_child(
            db,
            email=email,
            full_name=parent_full_name,
            phone=parent_phone,
            child=child,
            password=None,
        )
        token = secrets.token_urlsafe(32)
        invite = InviteToken(
            email=email,
            role_name=RoleName.PARENT.value,
            module_assignments=[],
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            created_by_user_id=created_by_user_id,
            linked_child_id=child.id,
            invite_metadata=_parent_invite_metadata(
                full_name=parent_full_name,
                phone=parent_phone,
            ),
        )
        db.add(invite)
        db.flush()
        invite_url = f"{settings.frontend_url}/invite/{token}"
        _send_parent_invite_email(email, invite_url, parent_full_name.strip(), child.full_name)
        return {
            "childId": child.id,
            "parentUserId": user.id,
            "inviteUrl": invite_url,
            "pendingEmail": email,
        }

    pwd = password or secrets.token_urlsafe(12)
    user, _pg = provision_parent_for_child(
        db,
        email=email,
        full_name=parent_full_name,
        phone=parent_phone,
        child=child,
        password=pwd,
    )
    return {
        "childId": child.id,
        "parentUserId": user.id,
        "inviteUrl": None,
    }


def _send_parent_invite_email(to: str, invite_url: str, parent_name: str, child_name: str) -> None:
    body = (
        f"Hi {parent_name},\n\n"
        f"You have been invited to the InsighteCase parent portal for {child_name}.\n\n"
        f"Create your account here:\n{invite_url}\n\n"
        "If you did not expect this, you can ignore this email.\n"
    )
    email_service.send_email(
        to=to,
        subject="You're invited to InsighteCase — Parent portal",
        body_text=body,
    )


def queue_parent_portal_invite_email(
    background_tasks,
    db: Session,
    *,
    to: str,
    invite_url: str,
    full_name: str,
    child_name: str,
    invite_id: int | None = None,
    force_resend: bool = False,
) -> None:
    from app.services.email.service import enqueue_portal_invite_email

    enqueue_portal_invite_email(
        background_tasks,
        db,
        to=to,
        invite_url=invite_url,
        full_name=full_name,
        role_label="Parent",
        intro_line=f"You have been invited to the Insighte parent portal for {child_name}.",
        recipient_role="parent",
        invite_id=invite_id,
        force_resend=force_resend,
    )


def issue_parent_invite(
    db: Session,
    parent_user_id: int,
    created_by_user_id: int,
    *,
    child_id: int | None = None,
    send_email: bool = True,
    background_tasks=None,
    force_resend: bool = False,
) -> str:
    from app.core.permissions import RoleName
    from app.services.invite_policy_service import assert_can_create_invite

    user = db.get(User, parent_user_id)
    if not user or RoleName.PARENT.value not in user.role_names:
        raise ValueError("Parent user not found")
    assert_can_create_invite(db, user.email, RoleName.PARENT.value)
    linked_child_id = child_id
    if linked_child_id is None:
        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == user.id)).first()
        if pg and pg.children:
            linked_child_id = pg.children[0].id
    token = secrets.token_urlsafe(32)
    invite = InviteToken(
        email=user.email,
        role_name=RoleName.PARENT.value,
        module_assignments=[],
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_user_id=created_by_user_id,
        linked_child_id=linked_child_id,
        invite_metadata=_parent_invite_metadata(
            full_name=user.full_name or user.email,
            phone=user.phone,
        ),
    )
    db.add(invite)
    db.flush()
    url = f"{settings.frontend_url}/invite/{token}"
    if send_email:
        child_name = "your child"
        if linked_child_id:
            ch = db.get(Child, linked_child_id)
            if ch:
                child_name = ch.full_name
        if background_tasks is not None:
            queue_parent_portal_invite_email(
                background_tasks,
                db,
                to=user.email,
                invite_url=url,
                full_name=user.full_name or user.email,
                child_name=child_name,
                invite_id=invite.id,
                force_resend=force_resend,
            )
        else:
            _send_parent_invite_email(user.email, url, user.full_name or user.email, child_name)
    return url


def lookup_parents(db: Session, search: str | None = None, limit: int = 25) -> list[dict]:
    from app.core.permissions import RoleName
    from app.models.role import Role

    q = (search or "").strip().lower()
    parents = db.scalars(
        select(User)
        .join(User.roles)
        .where(Role.name == RoleName.PARENT.value, User.is_active.is_(True))
        .options(selectinload(User.roles))
        .order_by(User.full_name)
    ).unique().all()
    rows: list[dict] = []
    for u in parents:
        hay = f"{u.full_name} {u.email} {u.phone or ''}".lower()
        if q and q not in hay:
            continue
        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == u.id)).first()
        children = []
        if pg:
            for c in pg.children:
                children.append({"childId": c.id, "childName": c.full_name})
        rows.append(
            {
                "userId": u.id,
                "fullName": u.full_name,
                "email": u.email,
                "phone": u.phone,
                "children": children,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def add_child_to_parent(
    db: Session,
    *,
    parent_user_id: int,
    first_name: str,
    last_name: str,
    date_of_birth=None,
) -> dict:
    from app.core.permissions import RoleName

    user = db.get(User, parent_user_id)
    if not user or RoleName.PARENT.value not in user.role_names:
        raise ValueError("Parent user not found")
    pg = db.scalars(
        select(ParentGuardian)
        .where(ParentGuardian.user_id == user.id)
        .options(selectinload(ParentGuardian.children))
    ).first()
    if not pg:
        pg = ParentGuardian(user_id=user.id)
        db.add(pg)
        db.flush()
    assert_no_duplicate_child_for_parent(
        pg,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
    )
    child = create_child(db, first_name, last_name, date_of_birth)
    if child not in pg.children:
        pg.children.append(child)
    db.flush()
    return {"id": child.id, "fullName": child.full_name, "parentUserId": user.id}


def link_child_to_parent_by_email(db: Session, child_id: int, parent_email: str) -> None:
    user = db.scalars(select(User).where(User.email == parent_email.lower())).first()
    if not user:
        return
    pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == user.id)).first()
    if not pg:
        pg = ParentGuardian(user_id=user.id)
        db.add(pg)
        db.flush()
    child = db.get(Child, child_id)
    if child and child not in pg.children:
        pg.children.append(child)
