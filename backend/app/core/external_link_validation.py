from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from app.models.case_document import ExternalLinkProvider

_ALLOWED_SCHEMES = frozenset({"https"})
_FOLDER_PATH = re.compile(r"drive\.google\.com/drive/folders", re.I)
_DOCS_PATH = re.compile(r"docs\.google\.com/document/", re.I)
_DRIVE_FILE = re.compile(r"drive\.google\.com/file/", re.I)
_DRIVE_OPEN = re.compile(r"drive\.google\.com/(?:open|uc)", re.I)


@dataclass(frozen=True)
class ValidatedExternalLink:
    url: str
    provider: str
    external_file_id: str | None


def validate_external_url(raw: str) -> ValidatedExternalLink:
    text = (raw or "").strip()
    if not text:
        raise ValueError("URL is required")
    parsed = urlparse(text)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError("Only https links are allowed")
    if not parsed.netloc:
        raise ValueError("Invalid URL")
    host_path = f"{parsed.netloc}{parsed.path}"
    if _FOLDER_PATH.search(host_path):
        raise ValueError("Google Drive folder links are not supported in this version")
    if not (_DOCS_PATH.search(host_path) or _DRIVE_FILE.search(host_path) or _DRIVE_OPEN.search(host_path)):
        raise ValueError("URL must be a Google Docs document or Google Drive file link")

    provider = ExternalLinkProvider.OTHER.value
    file_id: str | None = None
    if _DOCS_PATH.search(host_path):
        provider = ExternalLinkProvider.GOOGLE_DOCS.value
        m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", parsed.path)
        if m:
            file_id = m.group(1)
    elif _DRIVE_FILE.search(host_path):
        provider = ExternalLinkProvider.GOOGLE_DRIVE.value
        m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", parsed.path)
        if m:
            file_id = m.group(1)
    else:
        provider = ExternalLinkProvider.GOOGLE_DRIVE.value
        qs = parse_qs(parsed.query)
        ids = qs.get("id") or []
        if ids:
            file_id = ids[0]

    return ValidatedExternalLink(url=text, provider=provider, external_file_id=file_id)
