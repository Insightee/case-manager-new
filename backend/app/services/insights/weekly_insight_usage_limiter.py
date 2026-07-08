"""Weekly "Refresh Insights" usage cap — 2 free AI refreshes per case per therapist per week.

Uses `ClinicalSnapshot` (already the AI refresh cache table, `insight_type="case_insight_refresh"`)
as the usage ledger rather than `AiGenerationLog`: `AiGenerationLog.action` is hardcoded to
`"clinical_snapshot"` inside `ai_gateway_service.generate_clinical_snapshot` for every insight_type,
so it cannot distinguish this feature's calls from other snapshot generations. `ClinicalSnapshot`
already carries `case_id`, `generated_by_user_id`, `insight_type`, and `created_at`, and a row is
only ever written here on an actual AI call (cache hits reuse an existing row and do not count).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.clinical_snapshot import ClinicalSnapshot

WEEKLY_REFRESH_CAP = 2
INSIGHT_REFRESH_TYPE = "case_insight_refresh"


def _week_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_day - timedelta(days=start_of_day.weekday())


def get_usage(db: Session, *, case_id: int, user_id: int, now: datetime | None = None) -> dict:
    week_start = _week_start(now)
    used = int(
        db.scalar(
            select(func.count())
            .select_from(ClinicalSnapshot)
            .where(
                ClinicalSnapshot.case_id == case_id,
                ClinicalSnapshot.generated_by_user_id == user_id,
                ClinicalSnapshot.insight_type == INSIGHT_REFRESH_TYPE,
                ClinicalSnapshot.created_at >= week_start,
            )
        )
        or 0
    )
    resets_at = week_start + timedelta(days=7)
    return {
        "used": used,
        "cap": WEEKLY_REFRESH_CAP,
        "remaining": max(0, WEEKLY_REFRESH_CAP - used),
        "resets_at": resets_at.isoformat(),
    }


def has_capacity(db: Session, *, case_id: int, user_id: int, now: datetime | None = None) -> bool:
    return get_usage(db, case_id=case_id, user_id=user_id, now=now)["remaining"] > 0
