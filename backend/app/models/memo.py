from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Memo(Base):
    __tablename__ = "memos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memo_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    reply_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledgement_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    sender = relationship("User", foreign_keys=[from_user_id])
    recipient = relationship("User", foreign_keys=[to_user_id])
    messages = relationship("MemoMessage", back_populates="memo", cascade="all, delete-orphan")
    attachments = relationship("MemoAttachment", back_populates="memo", cascade="all, delete-orphan")
    audit_logs = relationship("MemoAuditLog", back_populates="memo", cascade="all, delete-orphan")


class MemoMessage(Base):
    __tablename__ = "memo_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memo_id: Mapped[int] = mapped_column(ForeignKey("memos.id"), nullable=False, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memo = relationship("Memo", back_populates="messages")
    author = relationship("User")
    attachments = relationship("MemoAttachment", back_populates="message", cascade="all, delete-orphan")


class MemoAttachment(Base):
    __tablename__ = "memo_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memo_id: Mapped[int] = mapped_column(ForeignKey("memos.id"), nullable=False, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("memo_messages.id"), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memo = relationship("Memo", back_populates="attachments")
    message = relationship("MemoMessage", back_populates="attachments")
    uploader = relationship("User")


class MemoAuditLog(Base):
    __tablename__ = "memo_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memo_id: Mapped[int] = mapped_column(ForeignKey("memos.id"), nullable=False, index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memo = relationship("Memo", back_populates="audit_logs")
    actor = relationship("User")
