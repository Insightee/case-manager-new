from __future__ import annotations

SUBMISSION_SUCCESS = frozenset(
    {
        "sent",
        "accepted",
        "delivered",
        "pending",
        "queued",
        "processed",
    }
)

RETRY_ELIGIBLE = frozenset(
    {
        "failed_retrying",
        "soft_bounced",
        "process_failed",
        "failed",  # legacy pre-migration rows
    }
)

TERMINAL_FAILURE = frozenset(
    {
        "failed_final",
        "hard_bounced",
    }
)

SKIPPED_PREFIX = "skipped_"


def is_submission_success(status: str | None) -> bool:
    return (status or "") in SUBMISSION_SUCCESS


def is_retry_eligible(status: str | None) -> bool:
    return (status or "") in RETRY_ELIGIBLE


def is_terminal_failure(status: str | None) -> bool:
    return (status or "") in TERMINAL_FAILURE


def is_skipped(status: str | None) -> bool:
    s = status or ""
    return s.startswith(SKIPPED_PREFIX)


def normalize_log_status(status: str | None) -> str:
    """Map legacy sent to accepted for internal comparisons."""
    if status == "sent":
        return "accepted"
    return status or "queued"
