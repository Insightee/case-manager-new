"""Collaborative Inputs — merges Parent, Case Manager, and School sources into actionable cards.

Fixes the long-standing `parent_input_status`/`school_input_status` TODO stubs in
`clinical_insights_preview_service.py` by actually reading `ParentGoalInput`, `DailyLog` parent
fields, `CaseManagerMeeting` notes, and `ClinicalReportSection` (`section_key="school_inputs"`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case_manager_meeting import CaseManagerMeeting
from app.models.clinical_report import ClinicalReport, ClinicalReportSection
from app.models.daily_log import DailyLog
from app.models.parent_goal_input import ParentGoalInput
from app.models.session import Session as TherapySession
from app.services.insights.helpers import make_insight

MAX_CARDS_PER_SOURCE = 5


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parent_goal_input_cards(db: Session, case_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ParentGoalInput)
        .where(ParentGoalInput.case_id == case_id)
        .order_by(ParentGoalInput.created_at.desc())
        .limit(MAX_CARDS_PER_SOURCE)
    ).all()
    cards = []
    for row in rows:
        if not (row.comment or "").strip():
            continue
        cards.append(
            {
                "id": f"parent_goal_input_{row.id}",
                "source": "Parent",
                "date": _iso(row.created_at),
                "input": row.comment.strip(),
                "linkedGoalId": row.goal_ref,
                "actionStatus": "incorporated" if row.review_status not in (None, "pending") else "not_incorporated",
            }
        )
    return cards


def _daily_log_parent_cards(db: Session, case_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(DailyLog)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(TherapySession.case_id == case_id)
        .order_by(DailyLog.id.desc())
        .limit(20)
    ).all()
    cards = []
    for log in rows:
        text = (log.parent_feedback or log.parent_notes or "").strip()
        if not text:
            continue
        cards.append(
            {
                "id": f"daily_log_parent_{log.id}",
                "source": "Parent",
                "date": _iso(log.parent_feedback_at or log.submitted_at),
                "input": text,
                "linkedGoalId": None,
                "actionStatus": "not_incorporated",
            }
        )
        if len(cards) >= MAX_CARDS_PER_SOURCE:
            break
    return cards


def _case_manager_meeting_cards(db: Session, case_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(CaseManagerMeeting)
        .where(CaseManagerMeeting.case_id == case_id)
        .order_by(CaseManagerMeeting.scheduled_date.desc())
        .limit(MAX_CARDS_PER_SOURCE)
    ).all()
    cards = []
    for meeting in rows:
        text = (meeting.notes_summary or meeting.notes_additional or "").strip()
        if not text:
            continue
        cards.append(
            {
                "id": f"cm_meeting_{meeting.id}",
                "source": "Case Manager",
                "date": meeting.scheduled_date.isoformat() if meeting.scheduled_date else None,
                "input": text,
                "linkedGoalId": None,
                "actionStatus": "not_incorporated" if meeting.notes_next_meeting_required else "incorporated",
            }
        )
    return cards


def _school_input_cards(db: Session, case_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ClinicalReportSection)
        .join(ClinicalReport, ClinicalReportSection.report_id == ClinicalReport.id)
        .where(ClinicalReport.case_id == case_id, ClinicalReportSection.section_key == "school_inputs")
        .order_by(ClinicalReportSection.updated_at.desc())
        .limit(MAX_CARDS_PER_SOURCE)
    ).all()
    cards = []
    for section in rows:
        text = (section.narrative_text or "").strip()
        if not text:
            continue
        cards.append(
            {
                "id": f"school_input_{section.id}",
                "source": "School",
                "date": _iso(section.updated_at),
                "input": text,
                "linkedGoalId": None,
                "actionStatus": "not_incorporated" if section.completion_status != "completed" else "incorporated",
            }
        )
    return cards


def build_collaborative_input_cards(db: Session, case_id: int) -> tuple[list[dict[str, Any]], list[dict]]:
    cards = (
        _parent_goal_input_cards(db, case_id)
        + _daily_log_parent_cards(db, case_id)
        + _case_manager_meeting_cards(db, case_id)
        + _school_input_cards(db, case_id)
    )
    cards.sort(key=lambda c: c.get("date") or "", reverse=True)

    insights = [
        make_insight(
            insight_id=card["id"],
            insight_type="collaborative_input",
            title=f"{card['source']} input",
            summary=card["input"][:280],
            status=card["actionStatus"],
            source_type="parent_input" if card["source"] == "Parent" else "collaborative_input",
            source_count=1,
            linked_goal_id=card.get("linkedGoalId"),
            recommended_action="Mark incorporated" if card["actionStatus"] == "not_incorporated" else None,
            review_path="cm_review",
        )
        for card in cards
    ]
    return cards, insights
