from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.core.config import settings


def safe_filename(name: str) -> str:
    base = Path(name or "image").name
    cleaned = re.sub(r"[^\w.\-]+", "_", base).strip("._")
    return cleaned[:200] or "image"


def _prefix_env() -> tuple[str, str]:
    prefix = (settings.storage_prefix or "insightcase").strip().strip("/")
    env = (settings.storage_environment or "development").strip().strip("/")
    return prefix, env


def build_object_key(category: str, *segments: str, filename: str) -> str:
    """Build a storage object key under {prefix}/{env}/{category}/…"""
    prefix, env = _prefix_env()
    safe = safe_filename(filename)
    unique = f"{uuid.uuid4().hex}_{safe}"
    cat = (category or "objects").strip().strip("/").lower()
    parts = [p.strip("/") for p in segments if p and str(p).strip("/")]
    path = "/".join([prefix, env, cat, *parts, unique])
    return path


def build_report_image_key(
    *,
    case_id: int,
    report_type: str,
    report_id: int,
    filename: str,
) -> str:
    rtype = (report_type or "monthly").strip().lower()
    return build_object_key(
        "report-images",
        f"case_{case_id}",
        rtype,
        f"report_{report_id}",
        filename=filename,
    )
