from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr


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
    invite_status: Optional[str] = None  # none | pending | expired | used
    last_invite_sent_at: Optional[str] = None
