from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.core.config import settings


def safe_filename(name: str) -> str:
    base = Path(name or "image").name
    cleaned = re.sub(r"[^\w.\-]+", "_", base).strip("._")
    return cleaned[:200] or "image"


def build_report_image_key(
    *,
    case_id: int,
    report_type: str,
    report_id: int,
    filename: str,
) -> str:
    safe = safe_filename(filename)
    unique = f"{uuid.uuid4().hex}_{safe}"
    prefix = (settings.storage_prefix or "insightcase").strip().strip("/")
    env = (settings.storage_environment or "development").strip().strip("/")
    rtype = (report_type or "monthly").strip().lower()
    return f"{prefix}/{env}/report-images/case_{case_id}/{rtype}/report_{report_id}/{unique}"
