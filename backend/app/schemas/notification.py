from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    title: str
    body: str
    is_read: bool
    created_at: datetime
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None

    model_config = {"from_attributes": True}
