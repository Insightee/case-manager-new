"""Anonymised session aggregates for a granted case."""
from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.services.integration.access import IntegrationPrincipal, require_case_grant, require_scope
from app.services.integration.rate_limit import check_rate_limit


def get_session_summary(
    db: Session,
    principal: IntegrationPrincipal,
    case_id: int,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    require_scope(principal, "sessions:summarize")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    require_case_grant(db, principal, case_id)

    sessions = list(db.scalars(select(TherapySession).where(TherapySession.case_id == case_id)).all())
    status_counts: Counter[str] = Counter()
    for s in sessions:
        key = s.status.value if hasattr(s.status, "value") else str(s.status)
        status_counts[key] += 1

    completed = status_counts.get(SessionStatus.COMPLETED.value, 0)
    cancelled = status_counts.get(SessionStatus.CANCELLED.value, 0)
    no_show = status_counts.get(SessionStatus.NO_SHOW.value, 0) + status_counts.get(
        SessionStatus.CLIENT_ABSENT.value, 0
    )

    log_count = db.scalar(
        select(func.count())
        .select_from(DailyLog)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(TherapySession.case_id == case_id)
    ) or 0

    payload = {
        "case_id": case_id,
        "session_count": len(sessions),
        "completed_count": completed,
        "cancelled_count": cancelled,
        "absence_or_no_show_count": no_show,
        "daily_log_count": int(log_count),
        "status_breakdown": dict(status_counts),
        # No free-text notes, GPS, therapist identity, or child PII.
    }
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.session_summary",
        entity_type="case",
        entity_id=case_id,
        case_id=case_id,
        new_value={"case_id": case_id, "session_count": len(sessions)},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload
