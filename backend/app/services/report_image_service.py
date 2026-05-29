from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import RoleName, case_scope_check
from app.models.report import MonthlyReport, ObservationReport, ReportStatus
from app.models.report_image import ReportImage
from app.models.user import User
from app.services import case_service, parent_reports_service
from app.services.parent_service import child_ids_for_parent
from app.storage.factory import get_storage_backend, get_storage_backend_for_provider
from app.storage.keys import build_report_image_key, safe_filename

ALLOWED_MIME = frozenset({"image/jpeg", "image/png", "image/webp"})

_JPEG_SIG = b"\xff\xd8\xff"
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_RIFF_WEBP = b"RIFF"


def _get_report(db: Session, report_type: str, report_id: int):
    if report_type == "monthly":
        return db.get(MonthlyReport, report_id)
    if report_type == "observation":
        return db.get(ObservationReport, report_id)
    return None


def _role_names(user: User) -> set[str]:
    names = getattr(user, "role_names", None)
    if names:
        return set(names)
    return {r.name for r in (user.roles or [])}


def _sniff_image_mime(raw: bytes):
    if len(raw) < 12:
        return None
    if raw[:3] == _JPEG_SIG[:3]:
        return "image/jpeg"
    if raw[:8] == _PNG_SIG:
        return "image/png"
    if raw[:4] == _RIFF_WEBP and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def _validate_image_bytes(raw: bytes, declared_mime: str) -> str:
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Image must be {settings.max_upload_bytes // (1024 * 1024)} MB or smaller",
        )
    if declared_mime not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")
    sniffed = _sniff_image_mime(raw)
    if sniffed is None:
        raise HTTPException(status_code=400, detail="File content is not a supported image")
    if sniffed != declared_mime:
        raise HTTPException(status_code=400, detail="Content-Type does not match file content")
    return sniffed


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


def _parent_linked_to_case(db: Session, user: User, case_id: int) -> bool:
    child_ids = child_ids_for_parent(db, user.id)
    if not child_ids:
        return False
    case = case_service.get_case(db, case_id)
    return bool(case and case.child_id in child_ids)


def _assert_can_view_report_image(db: Session, user: User, report, report_type: str) -> None:
    if not report:
        raise HTTPException(status_code=404, detail="Image not found")
    case = case_service.get_case(db, report.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Image not found")

    roles = _role_names(user)
    if RoleName.PARENT.value in roles:
        if not _parent_linked_to_case(db, user, report.case_id):
            raise HTTPException(status_code=404, detail="Image not found")
        if report_type == "observation":
            raise HTTPException(status_code=404, detail="Image not found")
        if not parent_reports_service.parent_can_see_monthly(report):
            raise HTTPException(status_code=404, detail="Image not found")
        return

    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Image not found")


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
    raw = await file.read()
    content_type = _validate_image_bytes(raw, content_type)

    original = file.filename or "image"
    storage_key = build_report_image_key(
        case_id=report.case_id,
        report_type=report_type,
        report_id=report_id,
        filename=original,
    )
    storage = get_storage_backend()
    result = storage.put_bytes(storage_key, raw, content_type)

    display_name = safe_filename(original)
    row = ReportImage(
        report_type=report_type,
        report_id=report_id,
        file_name=display_name,
        file_path=storage_key,
        storage_provider=result.provider,
        storage_key=storage_key,
        original_filename=original,
        mime_type=content_type,
        size_bytes=result.size_bytes,
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
    _assert_can_view_report_image(db, user, report, img.report_type)
    return img


def open_report_image_content(img: ReportImage) -> tuple[bytes, str, str]:
    mime = img.mime_type or "application/octet-stream"
    filename = img.file_name or img.original_filename or "image"

    if img.storage_key:
        backend = get_storage_backend_for_provider(img.storage_provider)
        try:
            data = backend.get_bytes(img.storage_key)
        except FileNotFoundError:
            logger.warning(
                "report_image missing in storage provider=%s key=%s image_id=%s",
                img.storage_provider,
                img.storage_key,
                img.id,
            )
            raise HTTPException(status_code=404, detail="File not found")
        return data, mime, filename

    if img.file_path:
        backend_root = Path(__file__).resolve().parents[2]
        candidates = [
            Path(img.file_path),
            backend_root / img.file_path,
            backend_root / "uploads" / "report_images" / Path(img.file_path).name,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate.read_bytes(), mime, filename

    logger.warning(
        "report_image has no storage_key or readable file_path image_id=%s",
        img.id,
    )
    raise HTTPException(status_code=404, detail="File not found")


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
