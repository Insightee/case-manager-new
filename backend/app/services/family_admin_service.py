from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.case import Case
from app.models.child import Child
from app.models.parent import ParentGuardian, parent_child_link
from app.models.user import InviteToken, User
from app.services import auth_service, email_service


def list_families(db: Session, search: str | None = None) -> list[dict]:
    children = db.scalars(select(Child).order_by(Child.first_name, Child.last_name)).all()
    parent_rows = db.scalars(
        select(ParentGuardian).options(
            selectinload(ParentGuardian.children),
            selectinload(ParentGuardian.user),
        )
    ).all()
    child_parents: dict[int, list[dict]] = {}
    for pg in parent_rows:
        u = pg.user
        info = {
            "parentId": pg.id,
            "userId": u.id,
            "parentName": u.full_name,
            "parentEmail": u.email,
            "parentPhone": u.phone,
        }
        seen_child: set[int] = set()
        for c in pg.children:
            if c.id in seen_child:
                continue
            seen_child.add(c.id)
            parents = child_parents.setdefault(c.id, [])
            if not any(p["userId"] == u.id for p in parents):
                parents.append(info)

    cases_by_child: dict[int, list[str]] = {}
    for case in db.scalars(select(Case)).all():
        cases_by_child.setdefault(case.child_id, []).append(case.case_code)

    now = datetime.now(timezone.utc)
    pending_by_child: dict[int, dict] = {}
    for inv in db.scalars(
        select(InviteToken).where(
            InviteToken.used_at.is_(None),
            InviteToken.expires_at > now,
            InviteToken.linked_child_id.isnot(None),
        )
    ).all():
        if inv.linked_child_id and inv.linked_child_id not in pending_by_child:
            pending_by_child[inv.linked_child_id] = {
                "pendingEmail": inv.email,
                "inviteExpiresAt": inv.expires_at.isoformat() if inv.expires_at else None,
            }

    result = []
    q = (search or "").strip().lower()
    for child in children:
        parents = child_parents.get(child.id, [])
        label = child.full_name
        if q:
            hay = f"{label} {' '.join(p['parentEmail'] for p in parents)} {' '.join(cases_by_child.get(child.id, []))}".lower()
            if q not in hay:
                continue
        pending = pending_by_child.get(child.id)
        result.append(
            {
                "childId": child.id,
                "childName": label,
                "firstName": child.first_name,
                "lastName": child.last_name,
                "dateOfBirth": child.date_of_birth.isoformat() if child.date_of_birth else None,
                "parents": parents,
                "caseCodes": cases_by_child.get(child.id, []),
                "hasParent": bool(parents),
                "pendingInvite": pending,
            }
        )
    return result


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

    email = parent_email.lower().strip()
    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing:
        raise ValueError("A user with this email already exists")

    child = create_child(db, child_first, child_last, child_dob)

    invite_url = None
    if send_invite:
        token = secrets.token_urlsafe(32)
        invite = InviteToken(
            email=email,
            role_name=RoleName.PARENT.value,
            module_assignments=[],
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            created_by_user_id=created_by_user_id,
            linked_child_id=child.id,
        )
        db.add(invite)
        db.flush()
        invite_url = f"{settings.frontend_url}/invite/{token}"
        _send_parent_invite_email(email, invite_url, parent_full_name.strip(), child.full_name)
    else:
        pwd = password or secrets.token_urlsafe(12)
        user = auth_service.create_user(
            db,
            email=email,
            password=pwd,
            full_name=parent_full_name.strip(),
            role_names=[RoleName.PARENT.value],
        )
        if parent_phone:
            user.phone = parent_phone
        pg = ParentGuardian(user_id=user.id)
        db.add(pg)
        db.flush()
        pg.children.append(child)
        db.flush()
        return {
            "childId": child.id,
            "parentUserId": user.id,
            "inviteUrl": None,
        }

    return {"childId": child.id, "parentUserId": None, "inviteUrl": invite_url, "pendingEmail": email}


def _send_parent_invite_email(to: str, invite_url: str, parent_name: str, child_name: str) -> None:
    body = (
        f"Hi {parent_name},\n\n"
        f"You have been invited to the InsightCase parent portal for {child_name}.\n\n"
        f"Create your account here:\n{invite_url}\n\n"
        "If you did not expect this, you can ignore this email.\n"
    )
    email_service.send_email(
        to=to,
        subject="You're invited to InsightCase — Parent portal",
        body_text=body,
    )


def issue_parent_invite(
    db: Session,
    parent_user_id: int,
    created_by_user_id: int,
    *,
    child_id: int | None = None,
    send_email: bool = True,
) -> str:
    from app.core.permissions import RoleName

    user = db.get(User, parent_user_id)
    if not user or RoleName.PARENT.value not in user.role_names:
        raise ValueError("Parent user not found")
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
        _send_parent_invite_email(user.email, url, user.full_name or user.email, child_name)
    return url


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
