"""Bulk consultant start-date import for 2026 leave credit setup."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import leave_policy_service as policy
from app.services.external_employee_id_service import normalize_external_employee_id
from app.services.therapist_profile_service import get_or_create_profile

BULK_LEAVE_IMPORT_YEAR = 2026

RowStatus = Literal["ok", "error"]

HEADER_ALIASES = {
    "external_employee_id": (
        "external_employee_id",
        "employee_id",
        "therapist_id",
        "therapist id",
        "id",
    ),
    "start_date": ("start_date", "employment_start_date", "start date", "consultant_start_date"),
}


@dataclass
class BulkLeaveRow:
    line_number: int
    external_employee_id: str
    start_date: date | None
    status: RowStatus
    error: str | None = None
    therapist_user_id: int | None = None
    therapist_name: str | None = None
    credits_earned: int | None = None
    paid_used: int | None = None
    leave_credit_pending: int | None = None


def _normalize_header(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_")


def _map_headers(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise ValueError("CSV must include a header row")
    mapped: dict[str, str] = {}
    for raw in fieldnames:
        norm = _normalize_header(raw)
        for key, aliases in HEADER_ALIASES.items():
            if norm in aliases and key not in mapped:
                mapped[key] = raw
                break
    missing = [k for k in HEADER_ALIASES if k not in mapped]
    if missing:
        raise ValueError(
            "CSV headers must include external_employee_id and start_date "
            f"(missing: {', '.join(missing)})"
        )
    return mapped


def _parse_date(value: str) -> date:
    text = (value or "").strip()
    if not text:
        raise ValueError("start_date is required")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid start_date: {text}")


def compute_credits_preview(
    db: Session,
    therapist_user_id: int,
    employment_start: date,
    *,
    year: int = BULK_LEAVE_IMPORT_YEAR,
    as_of: date | None = None,
) -> dict[str, int]:
    """Credits from start date; paid usage still comes from existing approved leave rows."""
    today = date.today()
    if as_of is None:
        as_of = date(year, 12, 31) if year < today.year else today
    credits_earned = policy.credits_earned_in_year(employment_start, year, as_of=as_of)
    detail = policy.computed_consumption_detail(db, therapist_user_id, year)
    paid_used = detail.paid
    return {
        "credits_earned": credits_earned,
        "paid_used": paid_used,
        "leave_credit_pending": max(credits_earned - paid_used, 0),
    }


def compute_usage_from_leaves_used(
    employment_start: date,
    leaves_used: int,
    *,
    year: int = BULK_LEAVE_IMPORT_YEAR,
    as_of: date | None = None,
) -> dict[str, int]:
    """Split leaves_used into paid and over-limit unpaid — reserved for future bulk usage column."""
    today = date.today()
    if as_of is None:
        as_of = date(year, 12, 31) if year < today.year else today
    credits_earned = policy.credits_earned_in_year(employment_start, year, as_of=as_of)
    paid_used = min(leaves_used, credits_earned)
    unpaid_over_limit = max(leaves_used - credits_earned, 0)
    return {
        "credits_earned": credits_earned,
        "paid_used": paid_used,
        "unpaid_over_limit": unpaid_over_limit,
        "unpaid_homecare": 0,
        "leave_credit_pending": max(credits_earned - paid_used, 0),
    }


def _resolve_therapist(db: Session, external_id: str) -> tuple[User | None, str | None]:
    normalized = normalize_external_employee_id(external_id)
    if not normalized:
        return None, "external_employee_id is required"
    user = db.scalars(select(User).where(User.external_employee_id == normalized)).first()
    if not user:
        return None, f"Therapist not found for ID {normalized}"
    role_names = user.role_names or []
    if "THERAPIST" not in role_names:
        return None, f"User {normalized} is not a therapist"
    return user, None


def parse_bulk_leave_csv(csv_text: str) -> list[dict[str, str]]:
    text = (csv_text or "").strip()
    if not text:
        raise ValueError("Paste or upload CSV data first")
    reader = csv.DictReader(io.StringIO(text))
    header_map = _map_headers(reader.fieldnames)
    rows: list[dict[str, str]] = []
    for line_number, raw in enumerate(reader, start=2):
        if not any((v or "").strip() for v in raw.values()):
            continue
        rows.append(
            {
                "line_number": str(line_number),
                "external_employee_id": (raw.get(header_map["external_employee_id"]) or "").strip(),
                "start_date": (raw.get(header_map["start_date"]) or "").strip(),
            }
        )
    if not rows:
        raise ValueError("No data rows found in CSV")
    return rows


def preview_bulk_leave_import(
    db: Session,
    csv_text: str,
    *,
    year: int = BULK_LEAVE_IMPORT_YEAR,
) -> dict:
    if year != BULK_LEAVE_IMPORT_YEAR:
        raise ValueError(f"Bulk leave import is only supported for {BULK_LEAVE_IMPORT_YEAR}")
    parsed_rows = parse_bulk_leave_csv(csv_text)
    preview_rows: list[dict] = []
    ok_count = 0
    for raw in parsed_rows:
        line_number = int(raw["line_number"])
        row = BulkLeaveRow(
            line_number=line_number,
            external_employee_id=raw["external_employee_id"],
            start_date=None,
            status="ok",
        )
        try:
            start_date = _parse_date(raw["start_date"])
            therapist, err = _resolve_therapist(db, raw["external_employee_id"])
            if err or not therapist:
                row.status = "error"
                row.error = err or "Therapist not found"
            else:
                preview = compute_credits_preview(db, therapist.id, start_date, year=year)
                row.start_date = start_date
                row.therapist_user_id = therapist.id
                row.therapist_name = therapist.full_name
                row.credits_earned = preview["credits_earned"]
                row.paid_used = preview["paid_used"]
                row.leave_credit_pending = preview["leave_credit_pending"]
                ok_count += 1
        except ValueError as exc:
            row.status = "error"
            row.error = str(exc)
        preview_rows.append(_serialize_row(row))
    return {
        "year": year,
        "mode": "start_date_only",
        "total_rows": len(preview_rows),
        "ok_rows": ok_count,
        "error_rows": len(preview_rows) - ok_count,
        "rows": preview_rows,
    }


def apply_bulk_leave_import(
    db: Session,
    csv_text: str,
    *,
    year: int = BULK_LEAVE_IMPORT_YEAR,
    actor_user_id: int,
) -> dict:
    preview = preview_bulk_leave_import(db, csv_text, year=year)
    if preview["error_rows"]:
        raise ValueError(
            f"{preview['error_rows']} row(s) have errors — fix the CSV before applying"
        )
    updated = 0
    for row in preview["rows"]:
        therapist = db.get(User, row["therapist_user_id"])
        if not therapist:
            continue
        profile = get_or_create_profile(db, therapist.id)
        profile.employment_start_date = date.fromisoformat(row["start_date"])
        snapshots = dict(profile.leave_year_snapshots or {})
        snapshots.pop(str(year), None)
        profile.leave_year_snapshots = snapshots or None
        profile.leave_balance_year = year
        profile.leave_backfill_updated_at = datetime.now(timezone.utc)
        profile.leave_backfill_updated_by_user_id = actor_user_id
        updated += 1
    return {
        "year": year,
        "mode": "start_date_only",
        "updated": updated,
        "rows": preview["rows"],
    }


def get_year_snapshot(profile: TherapistProfile | None, year: int) -> dict | None:
    if not profile or not profile.leave_year_snapshots:
        return None
    raw = profile.leave_year_snapshots.get(str(year))
    if not isinstance(raw, dict):
        return None
    return raw


def _serialize_row(row: BulkLeaveRow) -> dict:
    return {
        "line_number": row.line_number,
        "external_employee_id": row.external_employee_id,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "status": row.status,
        "error": row.error,
        "therapist_user_id": row.therapist_user_id,
        "therapist_name": row.therapist_name,
        "credits_earned": row.credits_earned,
        "paid_used": row.paid_used,
        "leave_credit_pending": row.leave_credit_pending,
    }
