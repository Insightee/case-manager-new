"""Canonical finance confidence policy (Stage 1 + Stage 2).

Single backend source for RECONCILED / PARTIAL / ESTIMATED / INCOMPLETE.
Frontend display/downgrade lives only in ``frontend/src/lib/financeConfidence.js``.

Rules:
- Pre-cutover (``FINANCE_CUTOVER_COMPLETE=false``): engine amounts never stay RECONCILED.
- Material source missing → INCOMPLETE.
- Aggregates never upgrade confidence (``lowest_confidence`` = worst rank).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

Confidence = str  # RECONCILED | PARTIAL | ESTIMATED | INCOMPLETE

LEVELS = ("RECONCILED", "PARTIAL", "ESTIMATED", "INCOMPLETE")

RANK: dict[str, int] = {
    "RECONCILED": 0,
    "PARTIAL": 1,
    "ESTIMATED": 2,
    "INCOMPLETE": 3,
}

CUTOVER_PENDING_REASON = (
    "Live financial cutover is pending — figures remain provisional (downgraded from reconciled)."
)


def cutover_complete() -> bool:
    return bool(settings.finance_cutover_complete)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clamp_for_cutover(confidence: Confidence, *, rewrite_reason: bool = False) -> tuple[Confidence, str | None]:
    """Downgrade RECONCILED → PARTIAL when cutover is incomplete.

    Returns ``(confidence, optional_reason_override)``. When ``rewrite_reason`` is
    False (count cards), reason text is left to the caller.
    """
    if confidence == "RECONCILED" and not cutover_complete():
        return "PARTIAL", CUTOVER_PENDING_REASON if rewrite_reason else None
    return confidence, None


def lowest_confidence(*levels: Confidence) -> Confidence:
    present = [c for c in levels if c in RANK]
    if not present:
        return "ESTIMATED"
    return max(present, key=lambda c: RANK[c])


def money_value(
    *,
    value: float | None,
    confidence: Confidence,
    confidence_reason: str,
    record_count: int,
    source_period: str,
    currency: str = "INR",
) -> dict[str, Any]:
    """Build MoneyValue. Never leave RECONCILED on engine amounts pre-cutover."""
    conf, reason_override = clamp_for_cutover(confidence, rewrite_reason=True)
    if reason_override is not None:
        confidence_reason = reason_override
    out: dict[str, Any] = {
        "currency": currency,
        "confidence": conf,
        "confidenceReason": confidence_reason,
        "recordCount": record_count,
        "sourcePeriod": source_period,
        "asOf": now_iso(),
    }
    if value is not None:
        out["value"] = round(float(value), 2)
    return out


def count_card(
    *,
    count: int,
    confidence: Confidence,
    confidence_reason: str,
    source_period: str,
    impact: dict[str, Any] | None = None,
    oldest_age_days: int | None = None,
    drill_queue: str,
) -> dict[str, Any]:
    """Count card with cutover clamp; preserves original reason text (legacy behavior)."""
    conf, _ = clamp_for_cutover(confidence, rewrite_reason=False)
    card: dict[str, Any] = {
        "count": int(count),
        "confidence": conf,
        "confidenceReason": confidence_reason,
        "sourcePeriod": source_period,
        "asOf": now_iso(),
        "drillQueue": drill_queue,
    }
    if impact is not None:
        card["impact"] = impact
    if oldest_age_days is not None:
        card["oldestAgeDays"] = oldest_age_days
    return card


def preview_confidence(*, material_missing: bool, has_suggested: bool) -> dict[str, str]:
    """Composer / preview confidence — never RECONCILED pre-cutover."""
    if material_missing:
        level = "INCOMPLETE"
        reason = "A material billing source is missing for this period."
    elif not cutover_complete():
        level = "PARTIAL"
        reason = "Pre-cutover engine amount — provisional until finance cutover."
    elif has_suggested:
        level = "PARTIAL"
        reason = "Based on ledger rows that are not yet production-reconciled."
    else:
        level = "ESTIMATED"
        reason = "Derived from incomplete bases — treat as provisional."
    return {"confidence": level, "confidenceReason": reason}
