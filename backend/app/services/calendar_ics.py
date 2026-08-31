from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def _ics_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\").replace("\r", "")
    return text.replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _ics_dt(date_value, time_value: time | None) -> str:
    if time_value is None:
        return f"{date_value.strftime('%Y%m%d')}T090000"
    return datetime.combine(date_value, time_value).strftime("%Y%m%dT%H%M%S")


def _timezone_block() -> str:
    return "\r\n".join(
        [
            "BEGIN:VTIMEZONE",
            "TZID:Asia/Kolkata",
            "BEGIN:STANDARD",
            "TZOFFSETFROM:+0530",
            "TZOFFSETTO:+0530",
            "TZNAME:IST",
            "DTSTART:19700101T000000",
            "END:STANDARD",
            "END:VTIMEZONE",
        ]
    )


def build_meeting_ics(
    meeting: Any,
    *,
    method: str = "REQUEST",
    sequence: int = 0,
    status: str | None = None,
) -> str:
    meeting_type = getattr(meeting, "meeting_type", None)
    type_label = getattr(meeting_type, "value", None) or meeting_type
    title = _ics_escape(getattr(meeting, "title", None) or type_label or "Case manager meeting")
    summary = title or "Case manager meeting"
    start_date = getattr(meeting, "scheduled_date", None)
    start_time = getattr(meeting, "scheduled_time", None)
    duration = int(getattr(meeting, "duration_minutes", 30) or 30)
    end_dt = None
    if start_date is not None:
        start_dt = datetime.combine(start_date, start_time or time(9, 0))
        end_dt = start_dt + __import__("datetime").timedelta(minutes=duration)
    uid = _ics_escape(str(getattr(meeting, "series_id", None) or f"meeting-{getattr(meeting, 'id', '0')}"))
    cm = getattr(meeting, "case_manager", None)
    organizer_email = getattr(cm, "email", None) or "noreply@insighte.in"
    organizer_name = getattr(cm, "full_name", None) or "Insighte"
    organizer = f"CN={_ics_escape(organizer_name)}:mailto:{_ics_escape(organizer_email)}"
    description_parts = []
    if getattr(meeting, "meeting_url", None):
        description_parts.append(f"Join: {meeting.meeting_url}")
    if getattr(meeting, "case_id", None):
        description_parts.append(f"Case ID: {meeting.case_id}")
    if getattr(meeting, "cancel_reason", None):
        description_parts.append(f"Cancelled: {meeting.cancel_reason}")
    description = "\\n".join(_ics_escape(part) for part in description_parts)
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Insighte//Case Manager//EN",
        "VERSION:2.0",
        f"METHOD:{method}",
        "CALSCALE:GREGORIAN",
        _timezone_block(),
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"SEQUENCE:{max(int(sequence), 0)}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;TZID=Asia/Kolkata:{_ics_dt(start_date, start_time)}",
        f"DTEND;TZID=Asia/Kolkata:{end_dt.strftime('%Y%m%dT%H%M%S') if end_dt else _ics_dt(start_date, start_time)}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        f"ORGANIZER;{organizer}",
    ]
    if getattr(meeting, "meeting_url", None):
        lines.append(f"LOCATION:{_ics_escape(getattr(meeting, 'meeting_url', None))}")
    if status:
        lines.append(f"STATUS:{status}")
    lines.extend(
        [
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )
    return "\r\n".join(lines) + "\r\n"


def meeting_ics_attachment(
    meeting: Any,
    *,
    method: str = "REQUEST",
    sequence: int = 0,
    status: str | None = None,
) -> dict[str, Any]:
    method_norm = method.upper()
    return {
        "filename": f"meeting-{getattr(meeting, 'series_id', getattr(meeting, 'id', 'event'))}.ics",
        "content_type": "text/calendar",
        "content_subtype": "calendar",
        "params": {"method": method_norm, "name": f"meeting-{getattr(meeting, 'id', 'event')}.ics"},
        "content": build_meeting_ics(meeting, method=method_norm, sequence=sequence, status=status),
    }

