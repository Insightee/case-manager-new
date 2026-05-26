from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_comment import CommentType, DocumentComment, DocumentEntityType
from app.models.report import MonthlyReport
from app.models.user import User
from app.schemas.admin_reports import ReportDocumentCommentRead


def list_monthly_comments(db: Session, report_id: int) -> list[ReportDocumentCommentRead]:
    rows = db.scalars(
        select(DocumentComment)
        .where(
            DocumentComment.entity_type == DocumentEntityType.MONTHLY_REPORT.value,
            DocumentComment.entity_id == report_id,
        )
        .order_by(DocumentComment.created_at.asc())
    ).all()
    out: list[ReportDocumentCommentRead] = []
    for row in rows:
        author = db.get(User, row.author_user_id)
        out.append(
            ReportDocumentCommentRead(
                id=row.id,
                comment_type=row.comment_type,
                body=row.body,
                author_name=author.full_name if author else None,
                created_at=row.created_at,
            )
        )
    return out


def add_monthly_comment(
    db: Session,
    report: MonthlyReport,
    user: User,
    *,
    body: str,
    comment_type: str = CommentType.GENERAL.value,
) -> ReportDocumentCommentRead:
    text = body.strip()
    if not text:
        raise ValueError("Comment body is required")
    row = DocumentComment(
        entity_type=DocumentEntityType.MONTHLY_REPORT.value,
        entity_id=report.id,
        case_id=report.case_id,
        author_user_id=user.id,
        comment_type=comment_type,
        body=text,
    )
    db.add(row)
    db.flush()
    return ReportDocumentCommentRead(
        id=row.id,
        comment_type=row.comment_type,
        body=row.body,
        author_name=user.full_name or user.email,
        created_at=row.created_at,
    )
