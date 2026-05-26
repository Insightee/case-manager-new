from __future__ import annotations

from typing import Optional, List

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class IncidentStatus(str, enum.Enum):
    REPORTED = "REPORTED"
    IN_REVIEW = "IN_REVIEW"
    ACTION_TAKEN = "ACTION_TAKEN"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class IncidentPriority(str, enum.Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


class IncidentPrimaryCategory(str, enum.Enum):
    CHILD_SAFETY_MEDICAL = "CHILD_SAFETY_MEDICAL"
    BEHAVIOUR_EMOTIONAL = "BEHAVIOUR_EMOTIONAL"
    SESSION_CLASSROOM_PROGRAM = "SESSION_CLASSROOM_PROGRAM"
    PARENT_SCHOOL_COMMUNICATION = "PARENT_SCHOOL_COMMUNICATION"
    THERAPIST_PARENT_CONDUCT = "THERAPIST_PARENT_CONDUCT"
    SAFEGUARDING_CONSENT_PRIVACY = "SAFEGUARDING_CONSENT_PRIVACY"
    LEGAL_POSH_CPP_POCSO = "LEGAL_POSH_CPP_POCSO"


class IncidentOwnerRole(str, enum.Enum):
    CASE_MANAGER = "CASE_MANAGER"
    HR = "HR"
    ADMIN = "ADMIN"


OPEN_INCIDENT_STATUSES = frozenset(
    {
        IncidentStatus.REPORTED,
        IncidentStatus.IN_REVIEW,
        IncidentStatus.ACTION_TAKEN,
        IncidentStatus.ESCALATED,
    }
)


def normalize_incident_status(value: str | IncidentStatus) -> IncidentStatus:
    if isinstance(value, IncidentStatus):
        return value
    raw = (value or "").strip().upper()
    legacy = {
        "OPEN": IncidentStatus.REPORTED,
        "INVESTIGATING": IncidentStatus.IN_REVIEW,
        "RESOLVED": IncidentStatus.ACTION_TAKEN,
    }
    if raw in legacy:
        return legacy[raw]
    try:
        return IncidentStatus(raw)
    except ValueError:
        return IncidentStatus.REPORTED


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_code: Mapped[Optional[str]] = mapped_column(String(32), unique=True, index=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"))
    reported_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, values_callable=lambda x: [e.value for e in x]),
        default=IncidentStatus.REPORTED,
    )
    primary_category: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(64))
    priority: Mapped[Optional[str]] = mapped_column(String(16), default=IncidentPriority.NORMAL.value)
    service_type: Mapped[Optional[str]] = mapped_column(String(32))
    incident_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    location: Mapped[Optional[str]] = mapped_column(String(32))
    immediate_action: Mapped[Optional[str]] = mapped_column(Text)
    child_safe: Mapped[Optional[str]] = mapped_column(String(8))
    parent_informed: Mapped[Optional[str]] = mapped_column(String(8))
    primary_owner_role: Mapped[Optional[str]] = mapped_column(String(32))
    tagged_roles: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    tagged_user_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    action_taken_note: Mapped[Optional[str]] = mapped_column(Text)
    last_owner_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sla_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[List["IncidentMessage"]] = relationship(
        "IncidentMessage",
        back_populates="incident",
        order_by="IncidentMessage.created_at",
        lazy="select",
    )
    attachments: Mapped[List["IncidentAttachment"]] = relationship(
        "IncidentAttachment",
        back_populates="incident",
        order_by="IncidentAttachment.created_at",
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


class IncidentAttachment(Base):
    __tablename__ = "incident_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), nullable=False, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incident_messages.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    incident: Mapped["Incident"] = relationship("Incident", back_populates="attachments")
