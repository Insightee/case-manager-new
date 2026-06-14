#!/usr/bin/env python3
"""Backfill parent users for legacy invites that have linked_child_id but no user row yet.

Usage (from backend/):
  python -m scripts.backfill_parent_provision_from_invites [--dry-run]
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import InviteToken, User
from app.services import family_admin_service


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not commit")
    args = parser.parse_args()

    db = SessionLocal()
    created = 0
    skipped = 0
    try:
        invites = db.scalars(
            select(InviteToken).where(
                InviteToken.used_at.is_(None),
                InviteToken.linked_child_id.isnot(None),
                InviteToken.role_name == "PARENT",
            )
        ).all()
        for invite in invites:
            email_l = invite.email.lower().strip()
            existing = db.scalars(select(User).where(User.email == email_l)).first()
            if existing:
                skipped += 1
                continue
            if args.dry_run:
                print(f"would backfill parent for invite {invite.id} ({email_l}) child {invite.linked_child_id}")
                created += 1
                continue
            user = family_admin_service.backfill_parent_from_invite(db, invite)
            if user:
                print(f"backfilled parent user {user.id} for invite {invite.id} ({email_l})")
                created += 1
            else:
                skipped += 1
        if args.dry_run:
            db.rollback()
            print(f"dry-run: would create {created}, skip {skipped}")
        else:
            db.commit()
            print(f"done: created {created}, skipped {skipped}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
