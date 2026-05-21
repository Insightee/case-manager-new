from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.permissions import case_scope_check
from app.models.report import MonthlyReport, ObservationReport, ReportStatus
from app.models.report_image import ReportImage
from app.services import case_service

UPLOAD_DIR = Path("uploads/report_images")
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_BYTES = 5 * 1024 * 1024


def _get_report(db: Session, report_type: str, report_id: int):
    if report_type == "monthly":
        return db.get(MonthlyReport, report_id)
    if report_type == "observation":
        return db.get(ObservationReport, report_id)
    return None


def _assert_can_edit_report(db: Session, user, report_type: str, report) -> None:
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Report not found")
    if report.therapist_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the report author can upload images")
    if report.status not in (ReportStatus.DRAFT, ReportStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Images can only be added to draft or rejected reports")


async def save_report_image(
    db: Session,
    user,
    report_type: str,
    report_id: int,
    file: UploadFile,
) -> dict:
    report = _get_report(db, report_type, report_id)
    _assert_can_edit_report(db, user, report_type, report)

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP, or GIF images are allowed")

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image must be 5 MB or smaller")

    ext = Path(file.filename or "image.jpg").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg" if "jpeg" in content_type or content_type == "image/jpeg" else ".png"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4()}{ext}"
    path = UPLOAD_DIR / stored
    path.write_bytes(raw)

    row = ReportImage(
        report_type=report_type,
        report_id=report_id,
        file_name=file.filename or stored,
        file_path=str(path),
        uploaded_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    return {"id": row.id, "url": f"/api/v1/reports/images/{row.id}"}


def get_image_for_user(db: Session, user, image_id: int) -> ReportImage:
    img = db.get(ReportImage, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    report = _get_report(db, img.report_type, img.report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Image not found")
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Image not found")
    return img


def sync_summary_from_body(report) -> None:
    """Keep summary column populated for list previews."""
    html = (report.body_html or "").strip()
    if not html:
        if report.plan_next_month:
            report.summary = (report.plan_next_month or "")[:300]
        return
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    report.summary = (text[:300] + "…") if len(text) > 300 else text or None
