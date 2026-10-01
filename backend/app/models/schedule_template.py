from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.scheduling_defaults import default_schedule_days, default_template_config as _default_template_config

DEFAULT_SCHEDULE_DAYS: dict[str, dict[str, Any]] = default_schedule_days()


def default_template_config() -> dict[str, Any]:
    return _default_template_config()


class TherapistScheduleTemplate(Base):
    __tablename__ = "therapist_schedule_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def get_config(self) -> dict[str, Any]:
        return json.loads(self.config_json)

    def set_config(self, config: dict[str, Any]) -> None:
        self.config_json = json.dumps(config)
