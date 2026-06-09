"""Session start resolution actions and conflict types."""

from __future__ import annotations

from enum import Enum


class RecommendedAction(str, Enum):
    CONTINUE_SESSION = "CONTINUE_SESSION"
    COMPLETE_LOG = "COMPLETE_LOG"
    EDIT_LOG = "EDIT_LOG"
    VIEW_EXISTING = "VIEW_EXISTING"
    REQUEST_ADDITIONAL_VISIT = "REQUEST_ADDITIONAL_VISIT"
    DUPLICATE_SAME_DAY = "DUPLICATE_SAME_DAY"
    START_SESSION = "START_SESSION"


class SessionStartConflict(Exception):
    """Raised when start must redirect to an existing visit."""

    def __init__(
        self,
        *,
        existing_session_id: int,
        current_status: str,
        recommended_action: RecommendedAction,
        message: str,
    ) -> None:
        self.existing_session_id = existing_session_id
        self.current_status = current_status
        self.recommended_action = recommended_action
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict:
        return {
            "existing_session_id": self.existing_session_id,
            "current_status": self.current_status,
            "recommended_action": self.recommended_action.value,
            "message": self.message,
        }
