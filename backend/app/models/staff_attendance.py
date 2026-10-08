from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class StaffAttendanceEntryType(str, enum.Enum):
    LIVE = "LIVE"
    FORGOT = "FORGOT"


class StaffAttendanceStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    AUTO_CLOSED = "AUTO_CLOSED"


class StaffAttendanceSegmentType(str, enum.Enum):
    WORK = "WORK"
    BREAK = "BREAK"


class StaffWorkMode(str, enum.Enum):
    OFFICE = "OFFICE"
    WFH = "WFH"


class StaffAttendance(Base):
    __tablename__ = "staff_attendance"
    __table_args__ = (UniqueConstraint("user_id", "work_date", "entry_type", name="uq_staff_attendance_user_day_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    entry_type: Mapped[StaffAttendanceEntryType] = mapped_column(
        Enum(StaffAttendanceEntryType), nullable=False, default=StaffAttendanceEntryType.LIVE
    )
    status: Mapped[StaffAttendanceStatus] = mapped_column(
        Enum(StaffAttendanceStatus), nullable=False, default=StaffAttendanceStatus.IN_PROGRESS
    )
    work_summary: Mapped[Optional[str]] = mapped_column(Text)
    forgot_reason: Mapped[Optional[str]] = mapped_column(Text)
    manual_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    manual_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_work_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_break_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    auto_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    work_mode: Mapped[Optional["StaffWorkMode"]] = mapped_column(Enum(StaffWorkMode), nullable=True)
    clock_in_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clock_in_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clock_in_accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distance_from_office_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clock_in_place_label: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    segments = relationship(
        "StaffAttendanceSegment",
        back_populates="attendance",
        cascade="all, delete-orphan",
        order_by="StaffAttendanceSegment.started_at",
    )


class StaffAttendanceSegment(Base):
    __tablename__ = "staff_attendance_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("staff_attendance.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_type: Mapped[StaffAttendanceSegmentType] = mapped_column(Enum(StaffAttendanceSegmentType), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    attendance = relationship("StaffAttendance", back_populates="segments")
