from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketCategory(str, enum.Enum):
    FINANCE = "FINANCE"
    HR = "HR"
    SERVICE = "SERVICE"
    POSH = "POSH"
    CPP = "CPP"
    OTHER = "OTHER"


class TicketTopic(str, enum.Enum):
    BILLING_PAYMENT = "BILLING_PAYMENT"
    THERAPIST = "THERAPIST"
    CASE_MANAGER = "CASE_MANAGER"
    OTHER = "OTHER"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), index=True)
    raised_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    product_module: Mapped[Optional[str]] = mapped_column(String(64))
    category: Mapped[TicketCategory] = mapped_column(Enum(TicketCategory), default=TicketCategory.OTHER, nullable=False)
    topic: Mapped[TicketTopic] = mapped_column(Enum(TicketTopic), default=TicketTopic.OTHER, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.OPEN, index=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parent_satisfaction_rating: Mapped[Optional[int]] = mapped_column(Integer)
    parent_resolution_feedback: Mapped[Optional[str]] = mapped_column(Text)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("TicketMessage", back_populates="ticket")
    attachments = relationship("TicketAttachment", back_populates="ticket")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id"), nullable=False, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket = relationship("SupportTicket", back_populates="messages")
    attachments = relationship("TicketAttachment", back_populates="message")
