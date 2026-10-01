"""Staff-only case operational notes — append-only journal with author metadata."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.models.case import Case
from app.models.case_operational_note import CaseOperationalNote
from app.models.user import User


def _note_to_dict(note: CaseOperationalNote, *, author_name: str | None) -> dict:
    return {
        "id": note.id,
        "case_id": note.case_id,
        "heading": note.heading,
        "body": note.body,
        "author_user_id": note.author_user_id,
        "author_name": author_name,
        "is_legacy_import": bool(note.is_legacy_import),
        "created_at": note.created_at,
    }


def _author_name(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.get(User, user_id)
    return user.full_name if user else None


def sync_case_notes_cache(db: Session, case: Case) -> None:
    """Keep cases.notes aligned with latest operational note for legacy integrations."""
    latest = db.scalars(
        select(CaseOperationalNote)
        .where(CaseOperationalNote.case_id == case.id)
        .order_by(CaseOperationalNote.created_at.desc(), CaseOperationalNote.id.desc())
        .limit(1)
    ).first()
    if latest is None:
        case.notes = None
        return
    case.notes = f"{latest.heading}\n\n{latest.body}".strip()


def list_notes_for_case(db: Session, *, case_id: int, limit: int = 100) -> list[dict]:
    rows = db.scalars(
        select(CaseOperationalNote)
        .where(CaseOperationalNote.case_id == case_id)
        .order_by(CaseOperationalNote.created_at.desc(), CaseOperationalNote.id.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    author_ids = {n.author_user_id for n in rows if n.author_user_id}
    names: dict[int, str] = {}
    if author_ids:
        for u in db.scalars(select(User).where(User.id.in_(author_ids))).all():
            names[u.id] = u.full_name or u.email
    out: list[dict] = []
    for note in rows:
        author_name = names.get(note.author_user_id) if note.author_user_id else None
        if note.is_legacy_import and not author_name:
            author_name = "Imported from previous record"
        out.append(_note_to_dict(note, author_name=author_name))
    return out


def latest_note_for_case(db: Session, *, case_id: int) -> dict | None:
    items = list_notes_for_case(db, case_id=case_id, limit=1)
    return items[0] if items else None


def create_note(
    db: Session,
    *,
    case: Case,
    heading: str,
    body: str,
    author: User,
) -> dict:
    heading_clean = (heading or "").strip()
    body_clean = (body or "").strip()
    if not heading_clean:
        raise ValueError("A heading is required for this note.")
    if not body_clean:
        raise ValueError("Looks like we still need a few details before we can save this.")
    note = CaseOperationalNote(
        case_id=case.id,
        heading=heading_clean,
        body=body_clean,
        author_user_id=author.id,
        is_legacy_import=False,
    )
    db.add(note)
    db.flush()
    sync_case_notes_cache(db, case)
    log_audit(
        db,
        actor_user_id=author.id,
        action="case_operational_note_created",
        entity_type="case_operational_note",
        entity_id=note.id,
        case_id=case.id,
        new_value={"heading": note.heading, "body": note.body[:500]},
    )
    return _note_to_dict(note, author_name=author.full_name or author.email)


def delete_note(db: Session, *, case: Case, note_id: int, actor: User) -> None:
    note = db.scalars(
        select(CaseOperationalNote).where(
            CaseOperationalNote.id == note_id,
            CaseOperationalNote.case_id == case.id,
        )
    ).first()
    if note is None:
        raise LookupError("Note not found")
    old = {"heading": note.heading, "body": note.body[:500]}
    db.delete(note)
    db.flush()
    sync_case_notes_cache(db, case)
    log_audit(
        db,
        actor_user_id=actor.id,
        action="case_operational_note_deleted",
        entity_type="case_operational_note",
        entity_id=note_id,
        case_id=case.id,
        old_value=old,
    )
