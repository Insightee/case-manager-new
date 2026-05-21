from __future__ import annotations

from typing import Optional, List

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class IncidentStatus(str, enum.Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"))
    reported_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[IncidentStatus] = mapped_column(Enum(IncidentStatus), default=IncidentStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[List["IncidentMessage"]] = relationship(
        "IncidentMessage",
        back_populates="incident",
        order_by="IncidentMessage.created_at",
        lazy="select",
    )
    reporter = relationship("User", foreign_keys=[reported_by_user_id], lazy="joined")
    assignee = relationship("User", foreign_keys=[assigned_to_user_id], lazy="select")


class IncidentMessage(Base):
    __tablename__ = "incident_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), nullable=False, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    incident: Mapped["Incident"] = relationship("Incident", back_populates="messages")
    author = relationship("User", foreign_keys=[author_user_id], lazy="joined")
