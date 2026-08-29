from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


class CaseBillingRateChange(Base):
    """Immutable audit of client billing / therapist remuneration amount changes.

    Case columns hold the *current* configured amounts (what the client is charged
    going forward). Payout/invoice calculators must resolve amounts as-of a service
    date via this history, not only the live case fields.

    source:
      FORM — admin billing PATCH
      AUDIT_BACKFILL — reconstructed from historical audit_events (idempotent)
      ASSIGNMENT_SNAPSHOT — locked outgoing-assignment pay (optional linkage)
    """

    __tablename__ = "case_billing_rate_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)

    previous_client_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    new_client_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    previous_therapist_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    new_therapist_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    client_effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    therapist_effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    previous_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON().with_variant(SQLiteJSON(), "sqlite"), nullable=True)
    new_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON().with_variant(SQLiteJSON(), "sqlite"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False, default="FORM", server_default="FORM", index=True)
    audit_event_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True, index=True)
    therapist_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    changed_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
