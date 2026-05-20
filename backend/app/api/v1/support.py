from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/support", tags=["support"])


@router.get("/info")
def support_info():
    return {
        "policies_bot_url": settings.policies_bot_url or None,
        "grievance_policy_url": settings.grievance_policy_url,
        "ticket_attachment_max_bytes": settings.ticket_attachment_max_bytes,
        "ticket_attachment_max_files": settings.ticket_attachment_max_files,
    }
