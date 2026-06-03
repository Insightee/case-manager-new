from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserProvisionResult(BaseModel):
    """Outcome of activate / invite-to-login (activation never depends on email)."""

    email: EmailStr
    role: Optional[str] = None
    user_created: bool = True
    user_active: bool = False
    invite_sent: bool = False
    invite_error: Optional[str] = None
    login_ready: bool = False
    invite_url: Optional[str] = None
    invite_status: Optional[str] = None
    last_invite_sent_at: Optional[str] = None
    email_delivery_status: Optional[str] = None
    email_attempt_count: Optional[int] = None
    last_email_status: Optional[str] = None
    last_email_sent_at: Optional[str] = None
    next_retry_at: Optional[str] = None
    resend_allowed_at: Optional[str] = None
    is_email_suppressed: bool = False
    suppression_reason: Optional[str] = None
    delivery_message: Optional[str] = None


class ClearEmailSuppressionBody(BaseModel):
    clear_reason: str = Field(..., min_length=3)
    corrected_email: Optional[EmailStr] = None
