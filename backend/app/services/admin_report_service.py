from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import get_allowed_case_product_modules
from app.core.pagination import normalize_pagination, paginated_response
from app.models.case import Case
from app.models.child import Child
from app.models.report import MonthlyReport, ObservationReport, ParentReviewStatus, ReportStatus
from app.models.review import Review, ReviewDecision
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.schemas.admin_reports import (
    AdminReportDetail,
    AdminReportListItem,
    AdminReportReviewHistoryItem,
    AdminReportSummary,
    AdminReportTypeSummary,
    BulkReportResult,
)
from app.core.module_write import guard_clinical_case
from app.services import case_service, parent_reports_service, report_service
from app.services.admin_scope_service import apply_case_scope


def _allowed_modules(user: User) -> list[str] | None:
    return get_allowed_case_product_modules(user)


def _paginate_joined(
    db: Session,
    stmt,
    *,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list, int]:
    page, page_size = normalize_pagination(page, page_size)
    subq = stmt.order_by(None).subquery()
    total = db.scalar(select(func.count()).select_from(subq)) or 0
    offset = (page - 1) * page_size
    rows = db.execute(stmt.offset(offset).limit(page_size)).all()
    return rows, int(total)


def _child_name(case: Case | None, child: Child | None = None) -> str | None:
    if child:
        return child.full_name
    if case and case.child:
        return case.child.full_name
    return None


def _therapist_name(user: User | None) -> str | None:
    if not user:
        return None
    return user.full_name or user.email


def _preview(text: str | None, limit: int = 120) -> str | None:
    if not text:
        return None
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def _monthly_base_stmt(db: Session, user: User):
    stmt = (
        select(MonthlyReport, Case, Child, User)
        .join(Case, MonthlyReport.case_id == Case.id)
        .join(Child, Case.child_id == Child.id)
        .join(User, MonthlyReport.therapist_user_id == User.id)
    )
    return apply_case_scope(stmt, user)


def _observation_base_stmt(db: Session, user: User):
    stmt = (
        select(ObservationReport, Case, Child, User)
        .join(Case, ObservationReport.case_id == Case.id)
        .join(Child, Case.child_id == Child.id)
        .join(User, ObservationReport.therapist_user_id == User.id)
    )
    return apply_case_scope(stmt, user)


def _apply_monthly_filters(
    stmt,
    *,
    status: ReportStatus | None,
    case_id: int | None,
    product_module: str | None,
    month: str | None,
    category: str | None,
    search: str | None,
    parent_review_status: str | None,
    queue_only: bool,
):
    if case_id is not None:
        stmt = stmt.where(MonthlyReport.case_id == case_id)
    if status is not None:
        stmt = stmt.where(MonthlyReport.status == status)
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    if month:
        stmt = stmt.where(MonthlyReport.month.ilike(f"%{month.strip()}%"))
    if category:
        stmt = stmt.where(MonthlyReport.category == category.strip())
    if parent_review_status:
        stmt = stmt.where(MonthlyReport.parent_review_status == parent_review_status)
    if queue_only:
        stmt = stmt.where(
            or_(
                MonthlyReport.status == ReportStatus.UNDER_REVIEW,
                MonthlyReport.parent_review_status == ParentReviewStatus.CHANGES_REQUESTED.value,
            )
        )
    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Case.case_code.ilike(q),
                Child.first_name.ilike(q),
                Child.last_name.ilike(q),
                MonthlyReport.month.ilike(q),
                MonthlyReport.summary.ilike(q),
                User.full_name.ilike(q),
                User.email.ilike(q),
            )
        )
    return stmt


def _apply_observation_filters(
    stmt,
    *,
    status: ReportStatus | None,
    case_id: int | None,
    product_module: str | None,
    category: str | None,
    search: str | None,
    queue_only: bool,
):
    if case_id is not None:
        stmt = stmt.where(ObservationReport.case_id == case_id)
    if status is not None:
        stmt = stmt.where(ObservationReport.status == status)
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    if category:
        stmt = stmt.where(ObservationReport.category == category.strip())
    if queue_only:
        stmt = stmt.where(ObservationReport.status == ReportStatus.UNDER_REVIEW)
    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Case.case_code.ilike(q),
                Child.first_name.ilike(q),
                Child.last_name.ilike(q),
                ObservationReport.title.ilike(q),
                ObservationReport.content.ilike(q),
                User.full_name.ilike(q),
                User.email.ilike(q),
            )
        )
    return stmt


def _serialize_monthly_row(row: tuple) -> AdminReportListItem:
    report, case, child, therapist = row
    return AdminReportListItem(
        report_type="monthly",
        id=report.id,
        case_id=report.case_id,
        case_code=case.case_code,
        child_name=_child_name(case, child),
        product_module=case.product_module,
        therapist_user_id=report.therapist_user_id,
        therapist_name=_therapist_name(therapist),
        label=report.month,
        status=report.status.value,
        visibility_status=report.visibility_status.value if report.visibility_status else None,
        parent_review_status=report.parent_review_status,
        parent_feedback=report.parent_feedback,
        content_preview=_preview(report.summary or report.body_html),
        category=report.category,
        updated_at=report.updated_at or report.created_at,
    )


def _serialize_observation_row(row: tuple) -> AdminReportListItem:
    report, case, child, therapist = row
    return AdminReportListItem(
        report_type="observation",
        id=report.id,
        case_id=report.case_id,
        case_code=case.case_code,
        child_name=_child_name(case, child),
        product_module=case.product_module,
        therapist_user_id=report.therapist_user_id,
        therapist_name=_therapist_name(therapist),
        label=report.title,
        status=report.status.value,
        visibility_status=report.visibility_status.value if report.visibility_status else None,
        content_preview=_preview(report.content or report.body_html),
        category=report.category,
        updated_at=report.created_at,
    )


def list_monthly_admin(
    db: Session,
    user: User,
    *,
    status: ReportStatus | None = None,
    case_id: int | None = None,
    product_module: str | None = None,
    month: str | None = None,
    category: str | None = None,
    search: str | None = None,
    parent_review_status: str | None = None,
    queue_only: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[AdminReportListItem], dict]:
    stmt = _monthly_base_stmt(db, user)
    stmt = _apply_monthly_filters(
        stmt,
        status=status,
        case_id=case_id,
        product_module=product_module,
        month=month,
        category=category,
        search=search,
        parent_review_status=parent_review_status,
        queue_only=queue_only,
    )
    stmt = stmt.order_by(MonthlyReport.updated_at.desc().nullslast(), MonthlyReport.created_at.desc())
    rows, total = _paginate_joined(db, stmt, page=page, page_size=page_size)
    items = [_serialize_monthly_row(r) for r in rows]
    return items, paginated_response(items, total, page, page_size)


def list_observation_admin(
    db: Session,
    user: User,
    *,
    status: ReportStatus | None = None,
    case_id: int | None = None,
    product_module: str | None = None,
    category: str | None = None,
    search: str | None = None,
    queue_only: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[AdminReportListItem], dict]:
    stmt = _observation_base_stmt(db, user)
    stmt = _apply_observation_filters(
        stmt,
        status=status,
        case_id=case_id,
        product_module=product_module,
        category=category,
        search=search,
        queue_only=queue_only,
    )
    stmt = stmt.order_by(ObservationReport.created_at.desc())
    rows, total = _paginate_joined(db, stmt, page=page, page_size=page_size)
    items = [_serialize_observation_row(r) for r in rows]
    return items, paginated_response(items, total, page, page_size)


def _status_counts(db: Session, model, user: User) -> AdminReportTypeSummary:
    base = select(model.status, func.count(model.id)).join(Case, model.case_id == Case.id)
    base = apply_case_scope(base, user)
    base = base.group_by(model.status)
    rows = db.execute(base).all()
    counts = {s.value if hasattr(s, "value") else s: c for s, c in rows}
    summary = AdminReportTypeSummary(
        draft=counts.get(ReportStatus.DRAFT.value, 0),
        under_review=counts.get(ReportStatus.UNDER_REVIEW.value, 0),
        rejected=counts.get(ReportStatus.REJECTED.value, 0),
        published=counts.get(ReportStatus.PUBLISHED.value, 0),
    )
    if model is MonthlyReport:
        chg = (
            select(func.count(MonthlyReport.id))
            .join(Case, MonthlyReport.case_id == Case.id)
            .where(MonthlyReport.parent_review_status == ParentReviewStatus.CHANGES_REQUESTED.value)
        )
        chg = apply_case_scope(chg, user)
        summary.parent_changes_requested = db.scalar(chg) or 0
    return summary


def list_queue_admin(
    db: Session,
    user: User,
    *,
    report_type: str | None = None,
    product_module: str | None = None,
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[AdminReportListItem], dict]:
    types: list[str]
    if report_type in (None, "", "all"):
        types = ["monthly", "observation"]
    elif report_type == "monthly":
        types = ["monthly"]
    elif report_type == "observation":
        types = ["observation"]
    else:
        types = ["monthly", "observation"]

    fetch_each = max(page_size, page * page_size)
    combined: list[AdminReportListItem] = []
    total = 0
    if "monthly" in types:
        monthly_items, monthly_meta = list_monthly_admin(
            db,
            user,
            product_module=product_module,
            category=category,
            search=search,
            queue_only=True,
            page=1,
            page_size=fetch_each,
        )
        combined.extend(monthly_items)
        total += int(monthly_meta.get("total") or 0)
    if "observation" in types:
        obs_items, obs_meta = list_observation_admin(
            db,
            user,
            product_module=product_module,
            category=category,
            search=search,
            queue_only=True,
            page=1,
            page_size=fetch_each,
        )
        combined.extend(obs_items)
        total += int(obs_meta.get("total") or 0)

    combined.sort(
        key=lambda x: x.updated_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    start = (page - 1) * page_size
    page_items = combined[start : start + page_size]
    return page_items, paginated_response(page_items, total, page, page_size)


def get_summary(db: Session, user: User) -> AdminReportSummary:
    monthly_summary = _status_counts(db, MonthlyReport, user)
    obs_summary = _status_counts(db, ObservationReport, user)
    queue_m = (
        select(func.count(MonthlyReport.id))
        .join(Case, MonthlyReport.case_id == Case.id)
        .where(
            or_(
                MonthlyReport.status == ReportStatus.UNDER_REVIEW,
                MonthlyReport.parent_review_status == ParentReviewStatus.CHANGES_REQUESTED.value,
            )
        )
    )
    queue_m = apply_case_scope(queue_m, user)
    monthly_queue = db.scalar(queue_m) or 0
    obs_queue_stmt = (
        select(func.count(ObservationReport.id))
        .join(Case, ObservationReport.case_id == Case.id)
        .where(ObservationReport.status == ReportStatus.UNDER_REVIEW)
    )
    obs_queue_stmt = apply_case_scope(obs_queue_stmt, user)
    obs_queue = db.scalar(obs_queue_stmt) or 0
    from app.services import admin_iep_service as admin_iep_svc

    iep_summary = admin_iep_svc.build_iep_dashboard(db, user)["summary"]
    iep_pending = (
        int(iep_summary.get("missing") or 0)
        + int(iep_summary.get("internal_only") or 0)
        + int(iep_summary.get("awaiting_ack") or 0)
    )
    return AdminReportSummary(
        monthly=monthly_summary,
        observation=obs_summary,
        queue_total=monthly_queue + obs_queue,
        iep_pending=iep_pending,
    )


def _review_history(db: Session, entity_type: str, entity_id: int) -> list[AdminReportReviewHistoryItem]:
    reviews = db.scalars(
        select(Review)
        .where(Review.entity_type == entity_type, Review.entity_id == entity_id)
        .order_by(Review.created_at.desc())
    ).all()
    out: list[AdminReportReviewHistoryItem] = []
    for r in reviews:
        reviewer = db.get(User, r.reviewer_user_id)
        decision = r.decision.value
        if decision == "REQUEST_REVIEW":
            decision = "SENT_FOR_REVIEW"
        elif decision == "NOTE":
            decision = "COMMENT"
        out.append(
            AdminReportReviewHistoryItem(
                id=r.id,
                decision=decision,
                comment=r.comment,
                reviewer_name=_therapist_name(reviewer),
                created_at=r.created_at,
            )
        )
    return out


def get_monthly_detail(db: Session, user: User, report_id: int) -> AdminReportDetail | None:
    stmt = _monthly_base_stmt(db, user).where(MonthlyReport.id == report_id)
    row = db.execute(stmt).first()
    if not row:
        return None
    report, case, child, therapist = row
    return AdminReportDetail(
        report_type="monthly",
        id=report.id,
        case_id=report.case_id,
        case_code=case.case_code,
        child_name=_child_name(case, child),
        product_module=case.product_module,
        therapist_user_id=report.therapist_user_id,
        therapist_name=_therapist_name(therapist),
        label=report.month,
        status=report.status.value,
        summary=report.summary,
        content=report.summary,
        body_html=report.body_html,
        plan_next_month=report.plan_next_month,
        category=report.category,
        sub_category=report.sub_category,
        report_date=report.report_date,
        reviewer_comment=report.reviewer_comment,
        visibility_status=report.visibility_status.value if report.visibility_status else None,
        parent_review_status=report.parent_review_status,
        parent_feedback=report.parent_feedback,
        parent_reviewed_at=report.parent_reviewed_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
        review_history=_review_history(db, "monthly_report", report.id),
    )


def get_observation_detail(db: Session, user: User, report_id: int) -> AdminReportDetail | None:
    stmt = _observation_base_stmt(db, user).where(ObservationReport.id == report_id)
    row = db.execute(stmt).first()
    if not row:
        return None
    report, case, child, therapist = row
    return AdminReportDetail(
        report_type="observation",
        id=report.id,
        case_id=report.case_id,
        case_code=case.case_code,
        child_name=_child_name(case, child),
        product_module=case.product_module,
        therapist_user_id=report.therapist_user_id,
        therapist_name=_therapist_name(therapist),
        label=report.title,
        status=report.status.value,
        content=report.content,
        body_html=report.body_html,
        plan_next_month=report.plan_next_month,
        category=report.category,
        sub_category=report.sub_category,
        report_date=report.report_date,
        visibility_status=report.visibility_status.value if report.visibility_status else None,
        created_at=report.created_at,
        updated_at=report.created_at,
        review_history=_review_history(db, "observation_report", report.id),
    )


def list_missing_monthly(
    db: Session,
    user: User,
    *,
    month: str,
    product_module: str | None = None,
) -> list[dict]:
    """Active cases without a CLIENT_MONTHLY report for the given month label."""
    from app.models.case import CaseStatus
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus

    stmt = select(Case).where(Case.status == CaseStatus.ACTIVE)
    stmt = apply_case_scope(stmt, user)
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    cases = db.scalars(stmt.options(selectinload(Case.child))).all()

    submitted_case_ids = set(
        db.scalars(
            select(MonthlyReport.case_id).where(
                MonthlyReport.month.ilike(f"%{month.strip()}%"),
                or_(MonthlyReport.category == "CLIENT_MONTHLY", MonthlyReport.category.is_(None)),
            )
        ).all()
    )

    out = []
    for case in cases:
        if case.id in submitted_case_ids:
            continue
        therapist_name = None
        assignment = db.scalars(
            select(CaseAssignment)
            .where(
                CaseAssignment.case_id == case.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
            .order_by(CaseAssignment.start_date.desc())
        ).first()
        if assignment:
            tu = db.get(User, assignment.therapist_user_id)
            therapist_name = _therapist_name(tu)
        out.append(
            {
                "case_id": case.id,
                "case_code": case.case_code,
                "child_name": _child_name(case, case.child),
                "therapist_name": therapist_name,
                "product_module": case.product_module,
            }
        )
    return out


def _can_bulk_approve_monthly(report: MonthlyReport) -> bool:
    if report.status == ReportStatus.UNDER_REVIEW:
        return True
    if (
        report.status == ReportStatus.PUBLISHED
        and report.parent_review_status == ParentReviewStatus.CHANGES_REQUESTED.value
    ):
        return True
    return False


def bulk_approve(
    db: Session,
    user: User,
    *,
    report_type: Literal["monthly", "observation"],
    ids: list[int],
    comment: str | None,
    visibility: VisibilityStatus | None,
) -> BulkReportResult:
    succeeded = 0
    failed = 0
    errors: list[str] = []
    for rid in ids:
        try:
            if report_type == "monthly":
                report = db.get(MonthlyReport, rid)
                if not report:
                    failed += 1
                    errors.append(f"Monthly report {rid} not found")
                    continue
                if not _can_bulk_approve_monthly(report):
                    failed += 1
                    errors.append(f"Monthly report {rid} is not approvable")
                    continue
                if (
                    report.status == ReportStatus.PUBLISHED
                    and report.parent_review_status == ParentReviewStatus.CHANGES_REQUESTED.value
                ):
                    parent_reports_service.resend_to_parent(db, report)
                    succeeded += 1
                else:
                    report_service.review_monthly_report(
                        db,
                        report,
                        user.id,
                        ReviewDecision.APPROVE,
                        comment,
                        visibility,
                    )
                    succeeded += 1
            else:
                report = db.get(ObservationReport, rid)
                if not report:
                    failed += 1
                    errors.append(f"Observation report {rid} not found")
                    continue
                case = case_service.get_case(db, report.case_id)
                if case:
                    guard_clinical_case(user, case, db, feature="reports")
                if report.status != ReportStatus.UNDER_REVIEW:
                    failed += 1
                    errors.append(f"Observation report {rid} is not under review")
                    continue
                report_service.review_observation_report(
                    db,
                    report,
                    user.id,
                    ReviewDecision.APPROVE,
                    comment,
                    visibility,
                )
                succeeded += 1
        except Exception as exc:
            failed += 1
            errors.append(f"Report {rid}: {exc}")
    db.flush()
    return BulkReportResult(succeeded=succeeded, failed=failed, errors=errors)


def bulk_reject(
    db: Session,
    user: User,
    *,
    report_type: Literal["monthly", "observation"],
    ids: list[int],
    comment: str,
) -> BulkReportResult:
    if not (comment or "").strip():
        return BulkReportResult(succeeded=0, failed=len(ids), errors=["Comment is required"])
    succeeded = 0
    failed = 0
    errors: list[str] = []
    for rid in ids:
        try:
            if report_type == "monthly":
                report = db.get(MonthlyReport, rid)
                if not report:
                    failed += 1
                    errors.append(f"Monthly report {rid} not found")
                    continue
                case = case_service.get_case(db, report.case_id)
                if case:
                    guard_clinical_case(user, case, db, feature="reports")
                if report.status != ReportStatus.UNDER_REVIEW:
                    failed += 1
                    errors.append(f"Monthly report {rid} is not under review")
                    continue
                report_service.review_monthly_report(
                    db,
                    report,
                    user.id,
                    ReviewDecision.REJECT,
                    comment.strip(),
                    None,
                )
                succeeded += 1
            else:
                report = db.get(ObservationReport, rid)
                if not report:
                    failed += 1
                    errors.append(f"Observation report {rid} not found")
                    continue
                case = case_service.get_case(db, report.case_id)
                if case:
                    guard_clinical_case(user, case, db, feature="reports")
                if report.status != ReportStatus.UNDER_REVIEW:
                    failed += 1
                    errors.append(f"Observation report {rid} is not under review")
                    continue
                report_service.review_observation_report(
                    db,
                    report,
                    user.id,
                    ReviewDecision.REJECT,
                    comment.strip(),
                    None,
                )
                succeeded += 1
        except Exception as exc:
            failed += 1
            errors.append(f"Report {rid}: {exc}")
    db.flush()
    return BulkReportResult(succeeded=succeeded, failed=failed, errors=errors)


def _export_rows(
    db: Session,
    user: User,
    *,
    report_type: str | None,
    queue_only: bool,
    status: ReportStatus | None,
    case_id: int | None,
    product_module: str | None,
    month: str | None,
    search: str | None,
    limit: int = 5000,
) -> list[dict]:
    rows: list[dict] = []
    if report_type in (None, "monthly", "all"):
        items, _ = list_monthly_admin(
            db,
            user,
            status=status,
            case_id=case_id,
            product_module=product_module,
            month=month,
            search=search,
            queue_only=queue_only,
            page=1,
            page_size=limit,
        )
        for it in items:
            rows.append(
                {
                    "type": "monthly",
                    "id": it.id,
                    "case_code": it.case_code,
                    "child_name": it.child_name,
                    "label": it.label,
                    "status": it.status,
                    "therapist": it.therapist_name,
                    "parent_review": it.parent_review_status or "",
                    "updated_at": it.updated_at.isoformat() if it.updated_at else "",
                }
            )
    if report_type in (None, "observation", "all"):
        items, _ = list_observation_admin(
            db,
            user,
            status=status,
            case_id=case_id,
            product_module=product_module,
            search=search,
            queue_only=queue_only,
            page=1,
            page_size=limit,
        )
        for it in items:
            rows.append(
                {
                    "type": "observation",
                    "id": it.id,
                    "case_code": it.case_code,
                    "child_name": it.child_name,
                    "label": it.label,
                    "status": it.status,
                    "therapist": it.therapist_name,
                    "parent_review": "",
                    "updated_at": it.updated_at.isoformat() if it.updated_at else "",
                }
            )
    return rows


def export_xlsx(
    db: Session,
    user: User,
    **filters,
) -> bytes:
    from openpyxl import Workbook

    rows = _export_rows(db, user, **filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "Reports"
    headers = ["Type", "ID", "Case", "Child", "Label", "Status", "Therapist", "Parent review", "Updated"]
    ws.append(headers)
    for r in rows:
        ws.append(
            [
                r["type"],
                r["id"],
                r["case_code"],
                r["child_name"],
                r["label"],
                r["status"],
                r["therapist"],
                r["parent_review"],
                r["updated_at"],
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_pdf(
    db: Session,
    user: User,
    **filters,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    rows = _export_rows(db, user, **filters)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    story = [Paragraph("Report management export", styles["Title"]), Spacer(1, 12)]
    data = [["Type", "Case", "Child", "Label", "Status", "Therapist", "Updated"]]
    for r in rows[:200]:
        data.append(
            [
                r["type"],
                r["case_code"] or "",
                (r["child_name"] or "")[:20],
                (r["label"] or "")[:24],
                r["status"],
                (r["therapist"] or "")[:18],
                (r["updated_at"] or "")[:16],
            ]
        )
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buf.getvalue()


_EDITABLE_STATUSES = frozenset(
    {ReportStatus.DRAFT, ReportStatus.UNDER_REVIEW, ReportStatus.REJECTED}
)


def staff_update_monthly(
    db: Session,
    user: User,
    report_id: int,
    payload: dict,
) -> AdminReportDetail | None:
    from app.services.report_image_service import sync_summary_from_body

    report = db.get(MonthlyReport, report_id)
    if not report:
        return None
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case):
        return None
    guard_clinical_case(user, case, db, feature="reports")
    if report.status not in _EDITABLE_STATUSES:
        raise ValueError("Report cannot be edited in its current status")
    for key, value in payload.items():
        if value is not None and hasattr(report, key):
            setattr(report, key, value)
    if payload.get("body_html") is not None:
        sync_summary_from_body(report)
    if report.status == ReportStatus.REJECTED:
        report.status = ReportStatus.UNDER_REVIEW
    db.flush()
    return get_monthly_detail(db, user, report_id)


def staff_update_observation(
    db: Session,
    user: User,
    report_id: int,
    payload: dict,
) -> AdminReportDetail | None:
    report = db.get(ObservationReport, report_id)
    if not report:
        return None
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case):
        return None
    guard_clinical_case(user, case, db, feature="reports")
    if report.status not in _EDITABLE_STATUSES:
        raise ValueError("Report cannot be edited in its current status")
    for key, value in payload.items():
        if value is not None and hasattr(report, key):
            setattr(report, key, value)
    if payload.get("body_html") and not report.content:
        report.content = (report.body_html or "")[:500]
    if report.status == ReportStatus.REJECTED:
        report.status = ReportStatus.UNDER_REVIEW
    db.flush()
    return get_observation_detail(db, user, report_id)
