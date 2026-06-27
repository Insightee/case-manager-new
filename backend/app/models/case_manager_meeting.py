from __future__ import annotations

import enum
from datetime import date, datetime, time
from typing import Optional, List

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, Time, Boolean, func
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MeetingType(str, enum.Enum):
    # Legacy Postgres meetingtype values (must match DB strings exactly).
    CLIENT_ONLY = "CLIENT_ONLY"
    CLIENT_AND_THERAPIST = "CLIENT_AND_THERAPIST"
    SUPERVISION = "SUPERVISION"
    # Current product values (SQLite / expanded Postgres enum).
    OBSERVATION_REVIEW = "OBSERVATION_REVIEW"
    OBSERVATION_CHECKLIST_REVIEW = "OBSERVATION_CHECKLIST_REVIEW"
    IEP_MEETING = "IEP_MEETING"
    MONTHLY_REPORT_REVIEW = "MONTHLY_REPORT_REVIEW"
    PROGRESS_REVIEW = "PROGRESS_REVIEW"
    PARENT_MEETING = "PARENT_MEETING"
    SCHOOL_MEETING = "SCHOOL_MEETING"
    THERAPIST_SUPPORT = "THERAPIST_SUPPORT"
    MENTOR_REVIEW = "MENTOR_REVIEW"
    INCIDENT_REVIEW = "INCIDENT_REVIEW"
    SUPPORT_TICKET_REVIEW = "SUPPORT_TICKET_REVIEW"
    ADMINISTRATIVE_MEETING = "ADMINISTRATIVE_MEETING"
    TRANSITION_PLANNING = "TRANSITION_PLANNING"
    CASE_CLOSURE_MEETING = "CASE_CLOSURE_MEETING"
    OTHER = "OTHER"


class MeetingStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"
    RESCHEDULED = "RESCHEDULED"


class CaseManagerMeeting(Base):
    __tablename__ = "case_manager_meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_manager_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    parent_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    therapist_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    mentor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    meeting_type: Mapped[MeetingType] = mapped_column(
        Enum(MeetingType), default=MeetingType.PARENT_MEETING, nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meeting_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    guest_emails_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    staff_attendee_user_ids_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Legacy notes fields (kept to avoid breaking database serialization of existing records)
    notes_concerns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_follow_up: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_other: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # New fields & details
    other_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rescheduled_from_id: Mapped[Optional[int]] = mapped_column(ForeignKey("case_manager_meetings.id"), nullable=True)
    reschedule_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Meeting Notes refactoring
    notes_outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # RESOLVED, FOLLOW_UP_REQUIRED, ESCALATED, NO_ACTION_REQUIRED
    notes_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_next_meeting_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=sa.false())
    notes_additional: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Linked Records
    linked_observation_report_id: Mapped[Optional[int]] = mapped_column(ForeignKey("observation_reports.id"), nullable=True)
    linked_observation_checklist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("observation_checklists.id"), nullable=True)
    linked_iep_id: Mapped[Optional[int]] = mapped_column(ForeignKey("iep_plans.id"), nullable=True)
    linked_monthly_report_id: Mapped[Optional[int]] = mapped_column(ForeignKey("monthly_reports.id"), nullable=True)
    linked_incident_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incidents.id"), nullable=True)
    linked_ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("support_tickets.id"), nullable=True)

    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus), default=MeetingStatus.SCHEDULED, nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    case_manager = relationship("User", foreign_keys=[case_manager_user_id], lazy="joined")
    case = relationship("Case", foreign_keys=[case_id], lazy="select")
    parent_user = relationship("User", foreign_keys=[parent_user_id], lazy="select")
    therapist_user = relationship("User", foreign_keys=[therapist_user_id], lazy="select")
    mentor_user = relationship("User", foreign_keys=[mentor_user_id], lazy="select")

    # Rescheduled hierarchy
    rescheduled_from = relationship("CaseManagerMeeting", remote_side="CaseManagerMeeting.id", foreign_keys=[rescheduled_from_id])

    # Linked records relationships
    linked_observation_report = relationship("ObservationReport", foreign_keys=[linked_observation_report_id], lazy="select")
    linked_observation_checklist = relationship("ObservationChecklist", foreign_keys=[linked_observation_checklist_id], lazy="select")
    linked_iep_plan = relationship("IepPlan", foreign_keys=[linked_iep_id], lazy="select")
    linked_monthly_report = relationship("MonthlyReport", foreign_keys=[linked_monthly_report_id], lazy="select")
    linked_incident = relationship("Incident", foreign_keys=[linked_incident_id], lazy="select")
    linked_ticket = relationship("SupportTicket", foreign_keys=[linked_ticket_id], lazy="select")

    # Actions list
    actions = relationship("MeetingAction", back_populates="meeting", cascade="all, delete-orphan")
