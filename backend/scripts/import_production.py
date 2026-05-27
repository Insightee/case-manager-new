#!/usr/bin/env python3
"""Production CSV import for therapists, clients, and cases.

Usage:
  cd backend
  python3 -m scripts.import_production --dir ../docs/import-templates --actor-email superadmin@demo.com --dry-run
  python3 -m scripts.import_production --dir ../docs/import-templates --actor-email superadmin@demo.com --commit

CSV files (in --dir):
  staff.csv, therapists.csv, clients.csv (or families.csv), cases.csv

Does not run demo_seed. Requires Alembic head applied.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.permissions import RoleName  # noqa: E402
from app.models.case import Case  # noqa: E402
from app.models.child import Child  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import allotment_service, auth_service, family_admin_service, therapist_onboarding_service  # noqa: E402


class ImportContext:
    """Tracks rows that would be created in dry-run so later files can resolve them."""

    def __init__(self) -> None:
        self.pending_user_emails: set[str] = set()
        self.pending_user_external_ids: set[str] = set()
        self.pending_child_external_ids: set[str] = set()
        self.pending_parent_emails: set[str] = set()
        self.row_errors: list[str] = []


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _split_pipe(value: str | None) -> list[str]:
    if not value or not str(value).strip():
        return []
    return [p.strip().lower() for p in str(value).replace("|", ",").split(",") if p.strip()]


def _err(ctx: ImportContext, file_label: str, row_num: int, message: str) -> None:
    ctx.row_errors.append(f"{file_label} row {row_num}: {message}")


def _resolve_user(
    db,
    ctx: ImportContext,
    *,
    email: str | None = None,
    external_id: str | None = None,
) -> User | None:
    if external_id:
        ext = external_id.strip()
        if ext in ctx.pending_user_external_ids:
            return None
        u = db.scalars(select(User).where(User.external_employee_id == ext)).first()
        if u:
            return u
    if email:
        em = email.strip().lower()
        if em in ctx.pending_user_emails:
            return None
        return db.scalars(select(User).where(User.email == em)).first()
    return None


def _resolve_child(
    db,
    ctx: ImportContext,
    *,
    external_id: str | None = None,
    child_first: str | None = None,
    child_last: str | None = None,
) -> Child | None:
    if external_id:
        ext = external_id.strip()
        if ext in ctx.pending_child_external_ids:
            return None
        c = db.scalars(select(Child).where(Child.external_client_id == ext)).first()
        if c:
            return c
        return None
    if child_first:
        stmt = select(Child).where(Child.first_name == child_first.strip())
        if child_last:
            stmt = stmt.where(Child.last_name == (child_last or "").strip())
        return db.scalars(stmt).first()
    return None


def _ensure_actor(db, email: str) -> User:
    user = db.scalars(select(User).where(User.email == email.lower())).first()
    if not user:
        raise SystemExit(f"Actor user not found: {email}")
    return user


def _clients_path(import_dir: Path) -> Path:
    clients = import_dir / "clients.csv"
    if clients.is_file():
        return clients
    return import_dir / "families.csv"


def import_staff(db, rows: list[dict], *, dry_run: bool, stats: dict, ctx: ImportContext) -> None:
    for i, row in enumerate(rows, start=2):
        email = (row.get("email") or "").strip().lower()
        if not email:
            _err(ctx, "staff.csv", i, "missing email")
            continue
        ext = (row.get("external_employee_id") or "").strip() or None
        existing = _resolve_user(db, ctx, email=email, external_id=ext)
        role_names = _split_pipe(row.get("role_names")) or [RoleName.CASE_MANAGER.value]
        modules = _split_pipe(row.get("module_assignments")) or ["homecare", "shadow_support"]
        if existing:
            if ext and not existing.external_employee_id:
                if not dry_run:
                    existing.external_employee_id = ext
            stats["staff_skipped"] += 1
            continue
        if dry_run:
            ctx.pending_user_emails.add(email)
            if ext:
                ctx.pending_user_external_ids.add(ext)
            stats["staff_created"] += 1
            continue
        user = auth_service.create_user(
            db,
            email=email,
            password=row.get("password") or "ChangeMe-Import1",
            full_name=(row.get("full_name") or email).strip(),
            role_names=role_names,
            module_assignments=modules,
        )
        if ext:
            user.external_employee_id = ext
        stats["staff_created"] += 1


def import_therapists(
    db,
    rows: list[dict],
    *,
    actor: User,
    dry_run: bool,
    stats: dict,
    default_cm_id: int,
    ctx: ImportContext,
) -> None:
    for i, row in enumerate(rows, start=2):
        email = (row.get("email") or "").strip().lower()
        if not email:
            _err(ctx, "therapists.csv", i, "missing email")
            continue
        ext = (row.get("external_employee_id") or "").strip() or None
        existing = _resolve_user(db, ctx, email=email, external_id=ext)
        if existing:
            if ext and not existing.external_employee_id and not dry_run:
                existing.external_employee_id = ext
            stats["therapists_skipped"] += 1
            continue
        cm_email = (row.get("primary_cm_email") or "").strip().lower()
        cm = _resolve_user(db, ctx, email=cm_email) if cm_email else None
        if cm_email and not cm and cm_email not in ctx.pending_user_emails:
            _err(ctx, "therapists.csv", i, f"case manager not found: {cm_email}")
            continue
        cm_id = cm.id if cm else default_cm_id
        services = _split_pipe(row.get("services_offered")) or ["homecare", "shadow_support"]
        if dry_run:
            ctx.pending_user_emails.add(email)
            if ext:
                ctx.pending_user_external_ids.add(ext)
            stats["therapists_created"] += 1
            continue
        try:
            result = therapist_onboarding_service.onboard_therapist(
                db,
                email=email,
                full_name=(row.get("full_name") or email).strip(),
                phone=(row.get("phone") or "").strip() or None,
                services_offered=services,
                module_assignments=services,
                mode="direct",
                password=row.get("password") or None,
                send_email=False,
                created_by_user_id=actor.id,
                primary_case_manager_user_id=cm_id,
            )
            user = db.get(User, result["user_id"])
            if user and ext:
                user.external_employee_id = ext
            stats["therapists_created"] += 1
        except Exception as exc:
            stats["therapists_errors"].append(f"row {i} {email}: {exc}")


def import_clients(
    db,
    rows: list[dict],
    *,
    actor: User,
    dry_run: bool,
    stats: dict,
    ctx: ImportContext,
    file_label: str,
) -> None:
    for i, row in enumerate(rows, start=2):
        ext = (row.get("external_client_id") or "").strip() or None
        parent_email = (row.get("parent_email") or "").strip().lower()
        if not parent_email:
            _err(ctx, file_label, i, "missing parent_email")
            continue
        child = _resolve_child(
            db,
            ctx,
            external_id=ext,
            child_first=row.get("child_first"),
            child_last=row.get("child_last"),
        )
        if child:
            if ext and not child.external_client_id and not dry_run:
                child.external_client_id = ext
            stats["clients_skipped"] += 1
            continue
        if ext and ext in ctx.pending_child_external_ids:
            stats["clients_skipped"] += 1
            continue
        if dry_run:
            if ext:
                ctx.pending_child_external_ids.add(ext)
            ctx.pending_parent_emails.add(parent_email)
            stats["clients_created"] += 1
            continue
        try:
            result = family_admin_service.create_family(
                db,
                parent_email=parent_email,
                parent_full_name=(row.get("parent_full_name") or row.get("parent_name") or parent_email).strip(),
                parent_phone=(row.get("phone") or row.get("parent_phone") or "").strip() or None,
                child_first=(row.get("child_first") or "").strip(),
                child_last=(row.get("child_last") or "").strip(),
                send_invite=str(row.get("send_invite", "false")).lower() in ("1", "true", "yes"),
                password=row.get("password") or None,
                created_by_user_id=actor.id,
            )
            child = db.get(Child, result["childId"])
            if child and ext:
                child.external_client_id = ext
            db.flush()
            stats["clients_created"] += 1
        except Exception as exc:
            stats["clients_errors"].append(f"row {i} {parent_email}: {exc}")


def import_cases(db, rows: list[dict], *, actor: User, dry_run: bool, stats: dict, ctx: ImportContext) -> None:
    for i, row in enumerate(rows, start=2):
        ext_ref = (row.get("external_case_ref") or "").strip() or None
        if ext_ref:
            existing_case = db.scalars(select(Case).where(Case.external_case_ref == ext_ref)).first()
            if existing_case:
                stats["cases_skipped"] += 1
                continue
        ext_client = (row.get("external_client_id") or "").strip() or None
        therapist_email = (row.get("therapist_email") or "").strip().lower()
        therapist = _resolve_user(db, ctx, email=therapist_email)
        child = _resolve_child(
            db,
            ctx,
            external_id=ext_client,
            child_first=row.get("child_first"),
            child_last=row.get("child_last"),
        )
        child_pending = bool(ext_client and ext_client in ctx.pending_child_external_ids)
        therapist_pending = bool(therapist_email and therapist_email in ctx.pending_user_emails)
        if not child and not child_pending:
            _err(ctx, "cases.csv", i, f"child not found (external_client_id={ext_client or 'n/a'})")
            continue
        if not therapist and not therapist_pending:
            _err(ctx, "cases.csv", i, f"therapist not found: {therapist_email}")
            continue
        if dry_run and (child_pending or therapist_pending) and (not child or not therapist):
            stats["cases_created"] += 1
            continue
        cm = _resolve_user(db, ctx, email=(row.get("cm_email") or row.get("case_manager_email") or "").strip().lower())
        payload: dict[str, Any] = {
            "child_id": child.id,
            "service_type": (row.get("service_type") or "Therapy").strip(),
            "product_module": (row.get("product_module") or "homecare").strip().lower(),
            "therapist_user_id": therapist.id,
            "case_manager_user_id": cm.id if cm else None,
            "case_code": (row.get("case_code") or "").strip() or None,
            "region": (row.get("region") or "").strip() or None,
            "notes": (row.get("notes") or "").strip() or None,
        }
        bt = (row.get("billing_type") or "").strip().upper()
        if bt:
            payload["billing_type"] = bt
            for key in (
                "client_rate_per_session_inr",
                "package_session_count",
                "package_amount_inr",
                "pay_share_pct",
                "therapist_fixed_pay_inr",
            ):
                if row.get(key):
                    payload[key] = float(row[key])
            cm_mode = (row.get("compensation_mode") or "").strip().upper()
            if cm_mode:
                payload["compensation_mode"] = cm_mode
            cbm = (row.get("client_billing_mode") or "").strip().upper()
            if cbm:
                payload["client_billing_mode"] = cbm
        if dry_run:
            stats["cases_created"] += 1
            continue
        try:
            result = allotment_service.allot_case(db, actor, payload)
            case_data = result["case"]
            case_id = case_data["id"] if isinstance(case_data, dict) else case_data.id
            case_obj = db.get(Case, case_id)
            if case_obj and ext_ref:
                case_obj.external_case_ref = ext_ref
            db.flush()
            stats["cases_created"] += 1
        except Exception as exc:
            stats["cases_errors"].append(f"row {i} {ext_ref or payload.get('case_code')}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import production CSV data")
    parser.add_argument("--dir", type=Path, required=True, help="Directory containing CSV files")
    parser.add_argument("--actor-email", default="superadmin@demo.com", help="Admin user email for audit/actions")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no commits")
    parser.add_argument("--commit", action="store_true", help="Persist changes (default if neither dry-run nor commit: dry-run)")
    args = parser.parse_args()

    dry_run = args.dry_run or not args.commit
    if args.dry_run and args.commit:
        raise SystemExit("Use either --dry-run or --commit, not both")

    stats: dict[str, Any] = {
        "staff_created": 0,
        "staff_skipped": 0,
        "therapists_created": 0,
        "therapists_skipped": 0,
        "therapists_errors": [],
        "clients_created": 0,
        "clients_skipped": 0,
        "clients_errors": [],
        "cases_created": 0,
        "cases_skipped": 0,
        "cases_errors": [],
    }
    ctx = ImportContext()

    db = SessionLocal()
    try:
        actor = _ensure_actor(db, args.actor_email)
        cm_default = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
        if not cm_default:
            cm_default = actor

        staff = _read_csv(args.dir / "staff.csv")
        therapists = _read_csv(args.dir / "therapists.csv")
        clients_path = _clients_path(args.dir)
        clients = _read_csv(clients_path)
        cases = _read_csv(args.dir / "cases.csv")

        import_staff(db, staff, dry_run=dry_run, stats=stats, ctx=ctx)
        import_therapists(db, therapists, actor=actor, dry_run=dry_run, stats=stats, default_cm_id=cm_default.id, ctx=ctx)
        import_clients(
            db,
            clients,
            actor=actor,
            dry_run=dry_run,
            stats=stats,
            ctx=ctx,
            file_label=clients_path.name,
        )
        import_cases(db, cases, actor=actor, dry_run=dry_run, stats=stats, ctx=ctx)

        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"Import summary ({mode}):")
    for key, val in stats.items():
        print(f"  {key}: {val}")
    if ctx.row_errors:
        print(f"\nRow validation errors ({len(ctx.row_errors)}):")
        for line in ctx.row_errors[:50]:
            print(f"  - {line}")
        if len(ctx.row_errors) > 50:
            print(f"  ... and {len(ctx.row_errors) - 50} more")
        sys.exit(1)


if __name__ == "__main__":
    main()
