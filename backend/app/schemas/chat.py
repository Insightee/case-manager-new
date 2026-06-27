from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MessageCreate(BaseModel):
    body: str


class MessageRead(BaseModel):
    id: int
    case_id: int
    sender_id: int
    recipient_id: int
    body: str
    attachment_path: Optional[str] = None
    attachment_name: Optional[str] = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseChatTab(BaseModel):
    case_id: int
    child_name: str
    case_code: str
    therapist_name: Optional[str] = None
    parent_name: Optional[str] = None
    unread_count: int
