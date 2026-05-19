from __future__ import annotations

import enum


class VisibilityStatus(str, enum.Enum):
    INTERNAL_ONLY = "INTERNAL_ONLY"
    APPROVED_FOR_PARENT = "APPROVED_FOR_PARENT"
    SHARED_WITH_PARENT = "SHARED_WITH_PARENT"
