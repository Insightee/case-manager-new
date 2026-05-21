from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.attachment import Attachment
from app.services.admin_scope_service import apply_case_scope
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.parent import ParentGuardian, parent_child_link
from app.models.user import User
from app.models.visibility import VisibilityStatus


def _derive_iep_status(att: Attachment | None) -> str:
    if not att:
        return "MISSING"
    vis = att.visibility_status
    if vis == VisibilityStatus.SHARED_WITH_PARENT:
        return "ACKNOWLEDGED"
    if vis == VisibilityStatus.APPROVED_FOR_PARENT:
        return "AWAITING_ACK"
    return "INTERNAL_ONLY"


def _parent_contacts_by_child_ids(db: Session, child_ids: list[int]) -> dict[int, list[str]]:
    if not child_ids:
        return {}
    rows = db.execute(
        select(parent_child_link.c.child_id, User.full_name, User.email)
        .select_from(parent_child_link)
        .join(ParentGuardian, parent_child_link.c.parent_guardian_id == ParentGuardian.id)
        .join(User, ParentGuardian.user_id == User.id)
        .where(parent_child_link.c.child_id.in_(child_ids))
    ).all()
    out: dict[int, list[str]] = {}
    for child_id, name, email in rows:
        label = f"{name} · {email}" if name and email else (email or name or "")
        if not label:
            continue
        bucket = out.setdefault(child_id, [])
        if label not in bucket:
            bucket.append(label)
    return out


def build_iep_dashboard(
    db: Session,
    user: User,
    *,
    status: str | None = None,
    product_module: str | None = None,
    search: str | None = None,
    include_closed: bool = False,
) -> dict:
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
    stmt = apply_case_scope(stmt, user)
    if not include_closed:
        stmt = stmt.where(Case.status != CaseStatus.CLOSED)
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    cases = list(db.scalars(stmt).all())

    if search:
        q = search.strip().lower()
        cases = [
            c
            for c in cases
            if q in (c.case_code or "").lower()
            or q in ((c.child.full_name if c.child else "") or "").lower()
            or q in (c.service_type or "").lower()
        ]

    case_ids = [c.id for c in cases]
    iep_attachments = []
    if case_ids:
        iep_attachments = db.scalars(
            select(Attachment)
            .where(Attachment.case_id.in_(case_ids), Attachment.entity_type == "iep")
            .order_by(Attachment.created_at.desc())
        ).all()
    latest_by_case: dict[int, Attachment] = {}
    for att in iep_attachments:
        if att.case_id not in latest_by_case:
            latest_by_case[att.case_id] = att

    uploader_ids = {a.uploaded_by_user_id for a in latest_by_case.values()}
    uploaders = {}
    if uploader_ids:
        for u in db.scalars(select(User).where(User.id.in_(uploader_ids))).all():
            uploaders[u.id] = u.full_name

    child_ids = [c.child_id for c in cases if c.child_id]
    parents_by_child = _parent_contacts_by_child_ids(db, child_ids)

    rows = []
    counts = {"MISSING": 0, "INTERNAL_ONLY": 0, "AWAITING_ACK": 0, "ACKNOWLEDGED": 0}
    for case in cases:
        att = latest_by_case.get(case.id)
        iep_status = _derive_iep_status(att)
        counts[iep_status] = counts.get(iep_status, 0) + 1
        if status and status.upper() != "ALL" and iep_status != status.upper():
            continue
        rows.append(
            {
                "case_id": case.id,
                "case_code": case.case_code,
                "child_name": case.child.full_name if case.child else None,
                "service_type": case.service_type,
                "product_module": case.product_module,
                "case_status": case.status.value,
                "iep_status": iep_status,
                "attachment_id": att.id if att else None,
                "file_name": att.file_name if att else None,
                "version": att.version if att else None,
                "visibility_status": att.visibility_status.value if att else None,
                "uploaded_at": att.created_at.isoformat() if att and att.created_at else None,
                "uploaded_by_name": uploaders.get(att.uploaded_by_user_id) if att else None,
                "parent_contacts": parents_by_child.get(case.child_id, []) if case.child_id else [],
            }
        )

    priority = {"AWAITING_ACK": 0, "MISSING": 1, "INTERNAL_ONLY": 2, "ACKNOWLEDGED": 3}
    rows.sort(key=lambda r: (priority.get(r["iep_status"], 9), r["case_code"] or ""))

    return {
        "summary": {
            "total_cases": len(cases),
            "missing": counts.get("MISSING", 0),
            "internal_only": counts.get("INTERNAL_ONLY", 0),
            "awaiting_ack": counts.get("AWAITING_ACK", 0),
            "acknowledged": counts.get("ACKNOWLEDGED", 0),
        },
        "rows": rows,
    }
