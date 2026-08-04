from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TherapistStatementDispute(Base):
    """A therapist's flag against their own monthly statement.

    Standalone, additive dispute-tracking record — NOT billing math. It never
    edits an amount; it records which sessions a therapist marks and why, so the
    finance statement queue can surface the disputed status to everyone.

    ``billing_disputes`` could not host this: it is parent-side
    (``client_invoice_id`` + ``parent_user_id`` NOT NULL). A therapist dispute
    has no client invoice or parent, so it needs its own home.
    """

    __tablename__ = "therapist_statement_disputes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    therapist_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    # Statement month, e.g. "2026-07". Present even before an invoice exists
    # (a therapist can dispute the provisional/pre-submit statement).
    month: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Set once the statement is a submitted invoice; nullable for provisional.
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id"), nullable=True, index=True
    )
    # Dispute lifecycle (plain string, not a DB enum): OPEN | UNDER_REVIEW |
    # RESOLVED | REJECTED. This is the dispute's own state — the invoice itself
    # reuses the existing InvoiceStatus.QUERIED flip, no parallel invoice status.
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    reason_code: Mapped[Optional[str]] = mapped_column(String(64))
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON array of session ids the therapist marked disputed. Lean choice;
    # revisit to a join table only if session-level dispute queries are ever
    # needed.
    disputed_session_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Snapshot of invoice.status before QUERIED flip — restored on finance resolve.
    prior_invoice_status: Mapped[Optional[str]] = mapped_column(String(32))
    admin_resolution: Mapped[Optional[str]] = mapped_column(Text)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
