from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from io import StringIO
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import extract, or_, select, func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.database import get_db
from app.core.permissions import RoleName, require_permission, user_has_permission, case_scope_check
from app.models.memo import Memo, MemoMessage, MemoAttachment, MemoAuditLog
from app.models.role import Role
from app.models.user import User
from app.storage.object_io import put_stored_bytes, stored_file_response

router = APIRouter(prefix="/memos", tags=["memos"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class MemoCreate(BaseModel):
    category: str
    priority: str
    recipient_type: str  # Therapist, Case Manager, Admin, Mentor
    recipient_ids: List[int] = Field(default_factory=list)
    bulk_target: Optional[str] = None  # ALL_HOMECARE_THERAPISTS, ALL_SHADOW_THERAPISTS, ALL_CASE_MANAGERS, or None
    subject: str
    details: str
    reply_required: bool = False
    acknowledgement_only: bool = False
    due_date: Optional[date] = None


class MessageCreate(BaseModel):
    body: str


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _can_manage_memos(user: User) -> bool:
    """Only SUPER_ADMIN, ADMIN, MODULE_ADMIN, HR, and FINANCE can send or manage memos."""
    if user_has_permission(user, "admin.override"):
        return True
    return any(
        role in user.role_names
        for role in ("SUPER_ADMIN", "ADMIN", "MODULE_ADMIN", "HR", "FINANCE")
    )


def _require_memo_management(user: User) -> None:
    if not _can_manage_memos(user):
        raise HTTPException(status_code=403, detail="Not allowed to manage memos")


def _get_memo_or_404(db: Session, memo_id: int) -> Memo:
    memo = db.get(Memo, memo_id)
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")
    return memo


def _can_access_memo(user: User, memo: Memo) -> bool:
    """Admin/HR can access all. Recipients can access their own."""
    if _can_manage_memos(user):
        return True
    return memo.to_user_id == user.id


def _require_memo_access(user: User, memo: Memo) -> None:
    if not _can_access_memo(user, memo):
        raise HTTPException(status_code=403, detail="Memo access denied")


def _log_memo_audit(db: Session, memo_id: int, actor_id: int, action: str, details: Optional[str] = None) -> None:
    audit = MemoAuditLog(
        memo_id=memo_id,
        actor_user_id=actor_id,
        action=action,
        details=details
    )
    db.add(audit)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_memo_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get dashboard stats for memos."""
    # Filter by user if not admin
    is_admin = _can_manage_memos(user)
    
    # Base queries
    stmt_open = select(func.count(Memo.id)).where(Memo.status == "OPEN")
    stmt_pending = select(func.count(Memo.id)).where(Memo.status == "PENDING_REPLY")
    stmt_review = select(func.count(Memo.id)).where(Memo.status == "UNDER_REVIEW")
    
    # Closed this month
    now = datetime.now()
    stmt_closed_month = select(func.count(Memo.id)).where(
        Memo.status == "CLOSED",
        extract("year", Memo.created_at) == now.year,
        extract("month", Memo.created_at) == now.month
    )

    if not is_admin:
        stmt_open = stmt_open.where(Memo.to_user_id == user.id)
        stmt_pending = stmt_pending.where(Memo.to_user_id == user.id)
        stmt_review = stmt_review.where(Memo.to_user_id == user.id)
        stmt_closed_month = stmt_closed_month.where(Memo.to_user_id == user.id)

    open_count = db.scalar(stmt_open) or 0
    pending_count = db.scalar(stmt_pending) or 0
    review_count = db.scalar(stmt_review) or 0
    closed_month_count = db.scalar(stmt_closed_month) or 0

    return {
        "open": open_count,
        "pending_reply": pending_count,
        "under_review": review_count,
        "closed_this_month": closed_month_count,
        # Total response required for recipient dashboard alert
        "awaiting_response": (open_count + pending_count) if not is_admin and (open_count + pending_count) > 0 else 0
    }


@router.get("/recipients")
def list_memo_recipients(
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Helper to return candidate recipients for issuing memos (Excludes Parents/Clients)."""
    _require_memo_management(user)
    
    stmt = (
        select(User)
        .join(User.roles)
        .where(Role.name.in_(("THERAPIST", "CASE_MANAGER", "MODULE_ADMIN", "HR", "FINANCE", "ADMIN", "SUPER_ADMIN", "SUPERVISOR")))
        .options(selectinload(User.roles))
        .order_by(User.full_name)
    )
    rows = db.scalars(stmt).unique().all()
    
    out = []
    q = (search or "").strip().lower()
    for u in rows:
        if not u.is_active:
            continue
        hay = f"{u.full_name} {u.email} {' '.join(u.role_names)}".lower()
        if q and q not in hay:
            continue
        out.append({
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "roles": u.role_names,
            "module_assignments": u.module_assignments or [],
        })
    return out


@router.get("/export")
def export_memos_csv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all memos as a CSV report for HR reviews/audits."""
    _require_memo_management(user)

    stmt = select(Memo).options(
        selectinload(Memo.recipient),
        selectinload(Memo.sender)
    ).order_by(Memo.created_at.desc())
    memos = db.scalars(stmt).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Memo ID", "Recipient Name", "Recipient Email", 
        "Category", "Priority", "Subject", "Status",
        "Created Date", "Reply Due Date", "Acknowledged Date", "Closed Date"
    ])

    for m in memos:
        # Resolve closed date from audit logs
        closed_date_raw = db.scalar(
            select(MemoAuditLog.created_at)
            .where(MemoAuditLog.memo_id == m.id, MemoAuditLog.action == "closed")
            .order_by(MemoAuditLog.created_at.desc())
            .limit(1)
        )
        closed_date = closed_date_raw.strftime("%Y-%m-%d %H:%M") if closed_date_raw else ""
        ack_date = m.acknowledged_at.strftime("%Y-%m-%d %H:%M") if m.acknowledged_at else ""

        writer.writerow([
            m.memo_code,
            m.recipient.full_name if m.recipient else f"User #{m.to_user_id}",
            m.recipient.email if m.recipient else "",
            m.category,
            m.priority,
            m.subject,
            m.status,
            m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "",
            m.due_date.isoformat() if m.due_date else "",
            ack_date,
            closed_date
        ])

    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=memo-report.csv"},
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def issue_memo(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Issue a new memo. Supports single, custom list, and bulk issuance."""
    _require_memo_management(user)

    content_type = request.headers.get("content-type", "")
    files: List[UploadFile] = []
    
    if "multipart/form-data" in content_type:
        form = await request.form()
        category = str(form.get("category") or "").strip()
        priority = str(form.get("priority") or "MEDIUM").strip()
        recipient_type = str(form.get("recipient_type") or "").strip()
        subject = str(form.get("subject") or "").strip()
        details = str(form.get("details") or "").strip()
        reply_required = form.get("reply_required") == "true"
        acknowledgement_only = form.get("acknowledgement_only") == "true"
        
        due_date_raw = form.get("due_date")
        due_date = date.fromisoformat(str(due_date_raw)) if due_date_raw else None
        
        bulk_target = form.get("bulk_target")
        if bulk_target == "null" or not bulk_target:
            bulk_target = None
            
        recipient_ids_raw = form.get("recipient_ids")
        if recipient_ids_raw:
            recipient_ids = [int(x) for x in json.loads(str(recipient_ids_raw))]
        else:
            recipient_ids = []
            
        # Parse files
        for key, value in form.multi_items():
            if hasattr(value, "read") and getattr(value, "filename", None):
                files.append(value)
    else:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        payload = MemoCreate(**data)
        category = payload.category
        priority = payload.priority
        recipient_type = payload.recipient_type
        subject = payload.subject
        details = payload.details
        reply_required = payload.reply_required
        acknowledgement_only = payload.acknowledgement_only
        due_date = payload.due_date
        bulk_target = payload.bulk_target
        recipient_ids = payload.recipient_ids

    if not category or not subject or not details:
        raise HTTPException(status_code=400, detail="Category, subject, and details are required")

    # Resolve recipient list
    resolved_recipient_ids = []
    if bulk_target:
        # Fetch target therapists or CMs
        if bulk_target == "ALL_HOMECARE_THERAPISTS":
            stmt = select(User).join(User.roles).where(Role.name == "THERAPIST", User.is_active == True)
            therapists = db.scalars(stmt).unique().all()
            resolved_recipient_ids = [u.id for u in therapists if u.module_assignments and "homecare" in u.module_assignments]
        elif bulk_target == "ALL_SHADOW_THERAPISTS":
            stmt = select(User).join(User.roles).where(Role.name == "THERAPIST", User.is_active == True)
            therapists = db.scalars(stmt).unique().all()
            resolved_recipient_ids = [u.id for u in therapists if u.module_assignments and "shadow_support" in u.module_assignments]
        elif bulk_target == "ALL_CASE_MANAGERS":
            stmt = select(User).join(User.roles).where(Role.name == "CASE_MANAGER", User.is_active == True)
            cms = db.scalars(stmt).unique().all()
            resolved_recipient_ids = [u.id for u in cms]
    else:
        resolved_recipient_ids = recipient_ids

    if not resolved_recipient_ids:
        raise HTTPException(status_code=400, detail="No valid recipients selected")

    # Validate that none of the recipients are parents
    parents_stmt = select(User.id).join(User.roles).where(Role.name == "PARENT", User.id.in_(resolved_recipient_ids))
    has_parents = db.scalars(parents_stmt).all()
    if has_parents:
        raise HTTPException(status_code=400, detail="Clients/Parents cannot be recipients of compliance memos")

    created_memos = []
    current_year = datetime.now().year
    
    # Process each memo creation
    for rid in resolved_recipient_ids:
        # Generate memo code
        year_prefix = f"MEM-{current_year}-"
        count = db.scalar(select(func.count(Memo.id)).where(Memo.memo_code.like(f"{year_prefix}%"))) or 0
        attempts = 0
        memo_code = ""
        while attempts < 10:
            candidate = f"MEM-{current_year}-{str(count + 1 + attempts).zfill(5)}"
            exists = db.scalar(select(Memo.id).where(Memo.memo_code == candidate))
            if not exists:
                memo_code = candidate
                break
            attempts += 1
            
        initial_status = "PENDING_REPLY" if reply_required else "OPEN"

        memo = Memo(
            memo_code=memo_code,
            from_user_id=user.id,
            to_user_id=rid,
            category=category,
            priority=priority,
            subject=subject,
            details=details,
            reply_required=reply_required,
            acknowledgement_only=acknowledgement_only,
            due_date=due_date,
            status=initial_status,
        )
        db.add(memo)
        db.flush()  # populate ID

        # Write audit log
        _log_memo_audit(db, memo.id, user.id, "created", f"Memo issued with code {memo_code}")

        # Store attachments
        if files:
            for f in files:
                filename = f.filename or "file"
                content_type = (f.content_type or "").split(";")[0].strip().lower()
                content = await f.read()
                
                storage_key, _provider = put_stored_bytes(
                    "memo-attachments",
                    f"memo_{memo.id}",
                    filename=filename,
                    data=content,
                    content_type=content_type,
                )
                
                att = MemoAttachment(
                    memo_id=memo.id,
                    file_name=filename,
                    file_path=storage_key,
                    mime_type=content_type,
                    size_bytes=len(content),
                    uploaded_by_user_id=user.id,
                )
                db.add(att)

        created_memos.append(memo)

    db.commit()

    # Send email notifications to each recipient
    for memo in created_memos:
        recipient = db.get(User, memo.to_user_id)
        if recipient and recipient.email:
            try:
                from app.services import email_service
                
                subject_line = f"New compliance/HR memo issued: {memo.subject}"
                body_text = (
                    f"Hello {recipient.full_name},\n\n"
                    f"A new compliance/HR memo has been issued to you by {user.full_name}.\n\n"
                    f"Memo Details:\n"
                    f"----------------------------------------\n"
                    f"Code: {memo.memo_code}\n"
                    f"Category: {memo.category}\n"
                    f"Priority: {memo.priority}\n"
                    f"Subject: {memo.subject}\n\n"
                    f"Details:\n{memo.details}\n"
                    f"----------------------------------------\n\n"
                    f"Reply Required: {'Yes' if memo.reply_required else 'No'}\n"
                )
                if memo.reply_required and memo.due_date:
                    body_text += f"Due Date: {memo.due_date.isoformat()}\n"
                body_text += (
                    f"\nPlease log in to the Case Manager portal to review and respond to this memo.\n\n"
                    f"Regards,\n"
                    f"Insighte Operations Team\n"
                )
                
                email_service.send_email(
                    to=recipient.email,
                    subject=subject_line,
                    body_text=body_text,
                    db=db,
                )
            except Exception as e:
                import logging
                logging.getLogger("uvicorn").error(f"Failed to send memo email notification: {e}")

    return {"status": "success", "count": len(created_memos)}


@router.get("")
def list_memos(
    category: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[int] = None,
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List memos. Admins see all, therapists/others see their own received memos."""
    stmt = select(Memo).options(
        selectinload(Memo.recipient),
        selectinload(Memo.sender)
    ).order_by(Memo.created_at.desc())

    if not _can_manage_memos(user):
        stmt = stmt.where(Memo.to_user_id == user.id)

    # Apply filters
    if category:
        stmt = stmt.where(Memo.category == category)
    if priority:
        stmt = stmt.where(Memo.priority == priority)
    if status:
        stmt = stmt.where(Memo.status == status)
    if month:
        stmt = stmt.where(extract("month", Memo.created_at) == month)
    
    if search:
        q = f"%{search.strip()}%"
        stmt = (
            stmt.join(User, Memo.to_user_id == User.id)
            .where(
                or_(
                    Memo.memo_code.ilike(q),
                    Memo.subject.ilike(q),
                    User.full_name.ilike(q)
                )
            )
        )

    memos = db.scalars(stmt).all()

    return [
        {
            "id": m.id,
            "memo_code": m.memo_code,
            "category": m.category,
            "priority": m.priority,
            "subject": m.subject,
            "status": m.status,
            "reply_required": m.reply_required,
            "acknowledgement_only": m.acknowledgement_only,
            "due_date": m.due_date.isoformat() if m.due_date else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "viewed": m.viewed_at is not None,
            "acknowledged": m.acknowledged_at is not None,
            "recipient_name": m.recipient.full_name if m.recipient else "",
            "sender_name": m.sender.full_name if m.sender else "System",
        }
        for m in memos
    ]


@router.get("/{memo_id}")
def get_memo_details(
    memo_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details for a single memo, including messages thread and audit logs."""
    memo = _get_memo_or_404(db, memo_id)
    _require_memo_access(user, memo)

    # Mark viewed if recipient opens it
    if memo.to_user_id == user.id and not memo.viewed_at:
        memo.viewed_at = datetime.now(timezone.utc)
        _log_memo_audit(db, memo.id, user.id, "viewed", "Memo viewed by recipient")
        db.commit()

    # Load messages thread
    msg_stmt = (
        select(MemoMessage)
        .where(MemoMessage.memo_id == memo_id)
        .options(
            selectinload(MemoMessage.author),
            selectinload(MemoMessage.attachments)
        )
        .order_by(MemoMessage.created_at.asc())
    )
    messages = db.scalars(msg_stmt).all()

    # Load attachments uploaded at the memo root level
    root_att_stmt = select(MemoAttachment).where(
        MemoAttachment.memo_id == memo_id,
        MemoAttachment.message_id.is_(None)
    ).options(selectinload(MemoAttachment.uploader))
    root_attachments = db.scalars(root_att_stmt).all()

    # Load audit trail log
    audit_stmt = (
        select(MemoAuditLog)
        .where(MemoAuditLog.memo_id == memo_id)
        .options(selectinload(MemoAuditLog.actor))
        .order_by(MemoAuditLog.created_at.asc())
    )
    audit_logs = db.scalars(audit_stmt).all()

    return {
        "id": memo.id,
        "memo_code": memo.memo_code,
        "category": memo.category,
        "priority": memo.priority,
        "subject": memo.subject,
        "details": memo.details,
        "status": memo.status,
        "reply_required": memo.reply_required,
        "acknowledgement_only": memo.acknowledgement_only,
        "due_date": memo.due_date.isoformat() if memo.due_date else None,
        "created_at": memo.created_at.isoformat() if memo.created_at else None,
        "viewed_at": memo.viewed_at.isoformat() if memo.viewed_at else None,
        "acknowledged_at": memo.acknowledged_at.isoformat() if memo.acknowledged_at else None,
        "recipient": {
            "id": memo.recipient.id,
            "full_name": memo.recipient.full_name,
            "email": memo.recipient.email,
        } if memo.recipient else None,
        "sender": {
            "id": memo.sender.id,
            "full_name": memo.sender.full_name,
            "email": memo.sender.email,
        } if memo.sender else None,
        "attachments": [
            {
                "id": a.id,
                "file_name": a.file_name,
                "mime_type": a.mime_type,
                "size_bytes": a.size_bytes,
                "uploaded_by": a.uploader.full_name if a.uploader else "",
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in root_attachments
        ],
        "messages": [
            {
                "id": msg.id,
                "body": msg.body,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "author": {
                    "id": msg.author.id,
                    "full_name": msg.author.full_name,
                    "role": "Recipient" if msg.author_user_id == memo.to_user_id else "Admin"
                } if msg.author else None,
                "attachments": [
                    {
                        "id": a.id,
                        "file_name": a.file_name,
                        "mime_type": a.mime_type,
                        "size_bytes": a.size_bytes,
                        "created_at": a.created_at.isoformat() if a.created_at else None,
                    }
                    for a in msg.attachments
                ]
            }
            for msg in messages
        ],
        "audit_logs": [
            {
                "id": l.id,
                "action": l.action,
                "details": l.details,
                "created_at": l.created_at.isoformat() if l.created_at else None,
                "actor_name": l.actor.full_name if l.actor else "System",
            }
            for l in audit_logs
        ]
    }


@router.post("/{memo_id}/messages", status_code=status.HTTP_201_CREATED)
async def add_memo_message(
    memo_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Post a new message reply. Moves status to UNDER_REVIEW if recipient replies, or requests clarification."""
    memo = _get_memo_or_404(db, memo_id)
    _require_memo_access(user, memo)

    content_type = request.headers.get("content-type", "")
    files: List[UploadFile] = []
    
    if "multipart/form-data" in content_type:
        form = await request.form()
        body = str(form.get("body") or "").strip()
        for key, value in form.multi_items():
            if hasattr(value, "read") and getattr(value, "filename", None):
                files.append(value)
    else:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        payload = MessageCreate(**data)
        body = payload.body.strip()

    if not body:
        raise HTTPException(status_code=400, detail="Message body is required")

    # Determine next status
    previous_status = memo.status
    if memo.to_user_id == user.id:
        # Recipient replies: moves to Under Review
        next_status = "UNDER_REVIEW"
        action_type = "replied"
        log_detail = f"Recipient submitted response. Status changed from {previous_status} to {next_status}"
    else:
        # Admin replies: usually requests clarification, changing status to PENDING_REPLY
        next_status = "PENDING_REPLY"
        action_type = "request_clarification"
        log_detail = f"Admin requested clarification. Status changed from {previous_status} to {next_status}"

    memo.status = next_status

    msg = MemoMessage(
        memo_id=memo.id,
        author_user_id=user.id,
        body=body,
    )
    db.add(msg)
    db.flush()

    # Log audit event
    _log_memo_audit(db, memo.id, user.id, action_type, log_detail)

    # Save attachments
    if files:
        for f in files:
            filename = f.filename or "file"
            content_type = (f.content_type or "").split(";")[0].strip().lower()
            content = await f.read()
            
            storage_key, _provider = put_stored_bytes(
                "memo-attachments",
                f"memo_{memo.id}_msg_{msg.id}",
                filename=filename,
                data=content,
                content_type=content_type,
            )
            
            att = MemoAttachment(
                memo_id=memo.id,
                message_id=msg.id,
                file_name=filename,
                file_path=storage_key,
                mime_type=content_type,
                size_bytes=len(content),
                uploaded_by_user_id=user.id,
            )
            db.add(att)

    db.commit()
    db.refresh(msg)
    return {
        "id": msg.id,
        "body": msg.body,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.post("/{memo_id}/acknowledge")
def acknowledge_memo(
    memo_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recipient acknowledges the memo. Closes it if acknowledgement only."""
    memo = _get_memo_or_404(db, memo_id)
    if memo.to_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the recipient can acknowledge this memo")

    memo.acknowledged_at = datetime.now(timezone.utc)
    log_detail = "Memo acknowledged by recipient"
    
    if memo.acknowledgement_only:
        previous_status = memo.status
        memo.status = "CLOSED"
        log_detail += f". Status changed from {previous_status} to CLOSED"

    _log_memo_audit(db, memo.id, user.id, "acknowledged", log_detail)
    db.commit()

    return {"status": "success", "acknowledged_at": memo.acknowledged_at.isoformat()}


@router.post("/{memo_id}/close")
def close_memo(
    memo_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin closes the memo."""
    _require_memo_management(user)
    memo = _get_memo_or_404(db, memo_id)

    previous_status = memo.status
    memo.status = "CLOSED"

    _log_memo_audit(db, memo.id, user.id, "closed", f"Memo closed by admin. Previous status: {previous_status}")
    db.commit()

    return {"status": "success"}


@router.post("/{memo_id}/reopen")
def reopen_memo(
    memo_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin reopens the memo."""
    _require_memo_management(user)
    memo = _get_memo_or_404(db, memo_id)

    previous_status = memo.status
    next_status = "PENDING_REPLY" if memo.reply_required else "OPEN"
    memo.status = next_status

    _log_memo_audit(db, memo.id, user.id, "reopened", f"Memo reopened by admin. Status changed from {previous_status} to {next_status}")
    db.commit()

    return {"status": "success"}


@router.get("/{memo_id}/attachments/{attachment_id}")
def download_memo_attachment(
    memo_id: int,
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download memo or reply attachment."""
    memo = _get_memo_or_404(db, memo_id)
    _require_memo_access(user, memo)

    att = db.get(MemoAttachment, attachment_id)
    if not att or att.memo_id != memo_id:
        raise HTTPException(status_code=404, detail="Attachment not found")

    return stored_file_response(
        att.file_path,
        filename=att.file_name,
        media_type=att.mime_type
    )
