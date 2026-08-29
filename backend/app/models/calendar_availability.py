from __future__ import annotations

import enum
from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Time,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AvailabilityExceptionType(str, enum.Enum):
    CLOSED = "CLOSED"
    CUSTOM = "CUSTOM"


class CalendarProvider(str, enum.Enum):
    GOOGLE = "google"


class StaffAvailabilityRule(Base):
    __tablename__ = "staff_availability_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    slot_granularity_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", lazy="select")


class StaffAvailabilityException(Base):
    __tablename__ = "staff_availability_exceptions"
    __table_args__ = (
        UniqueConstraint("user_id", "date", "type", "start_time", "end_time", name="uq_staff_availability_exceptions"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    type: Mapped[AvailabilityExceptionType] = mapped_column(
        Enum(AvailabilityExceptionType), nullable=False, default=AvailabilityExceptionType.CLOSED
    )
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", lazy="select")


class StaffBookingPolicy(Base):
    __tablename__ = "staff_booking_policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    min_notice_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120, server_default="120")
    max_days_ahead: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default="60")
    buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    allowed_durations_json: Mapped[list] = mapped_column(JSON, nullable=False, default=lambda: [30, 45, 60, 90])
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", lazy="select")

    @property
    def allowed_durations(self) -> list[int]:
        values = self.allowed_durations_json or []
        return [int(v) for v in values if str(v).strip()]


class UserCalendarConnection(Base):
    __tablename__ = "user_calendar_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_calendar_connections_user_provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default=CalendarProvider.GOOGLE.value, index=True)
    google_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freebusy_enabled: Mapped[bool] = mapped_column(default=True, nullable=False, server_default="true")
    last_sync_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", lazy="select")

    @property
    def is_connected(self) -> bool:
        return self.revoked_at is None and bool(self.refresh_token_encrypted or self.access_token_encrypted)

