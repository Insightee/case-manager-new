"""Structured billing calculation errors surfaced to API callers (no amount changes)."""
from __future__ import annotations

from fastapi import HTTPException

from app.models.case import Case

MISSING_PACKAGE_COUNT_CODE = "MISSING_PACKAGE_COUNT"


class MissingPackageCountError(ValueError):
    """PACKAGE case has no positive package_session_count."""

    code = MISSING_PACKAGE_COUNT_CODE

    def __init__(self, case: Case) -> None:
        self.case_id = int(case.id)
        self.case_code = str(case.case_code or case.id)
        super().__init__(self.code)

    def user_message(self) -> str:
        return (
            f"Case {self.case_code} is missing package session count. "
            "Set it on the case billing profile before exporting this invoice."
        )

    def as_detail(self) -> dict:
        return {
            "code": self.code,
            "message": self.user_message(),
            "caseId": self.case_id,
            "caseCode": self.case_code,
        }


def raise_http_for_billing_calc_error(exc: BaseException) -> None:
    """Map known billing calc errors to HTTP responses; re-raise anything else."""
    if isinstance(exc, MissingPackageCountError):
        raise HTTPException(status_code=422, detail=exc.as_detail()) from exc
    if isinstance(exc, ValueError) and str(exc).strip() == MISSING_PACKAGE_COUNT_CODE:
        raise HTTPException(
            status_code=422,
            detail={
                "code": MISSING_PACKAGE_COUNT_CODE,
                "message": (
                    "A package-billed case is missing package session count. "
                    "Set it on the case billing profile before exporting this invoice."
                ),
            },
        ) from exc
    raise exc
