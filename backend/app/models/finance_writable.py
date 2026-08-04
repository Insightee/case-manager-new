"""Finance writable Loop 2 — correction proposals, payout deductions, structured notes."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FinanceCorrectionProposalType(str, enum.Enum):
    CORRECT_RESHARE = "CORRECT_RESHARE"
    LINKED_AMOUNT_EDIT = "LINKED_AMOUNT_EDIT"
    PAYOUT_ONLY_EDIT = "PAYOUT_ONLY_EDIT"


class FinanceWrongSide(str, enum.Enum):
    INVOICE_WRONG = "INVOICE_WRONG"
    RECORD_WRONG = "RECORD_WRONG"


class FinanceProposalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class CaseFinanceNoteScope(str, enum.Enum):
    CRM = "CRM"
    HR = "HR"
    FINANCE = "FINANCE"


class CaseFinanceNoteType(str, enum.Enum):
    TRANSITION = "TRANSITION"
    RETAINER = "RETAINER"
    DEDUCTION = "DEDUCTION"
    NOTICE_PERIOD = "NOTICE_PERIOD"
    OTHER = "OTHER"


class FinancePayoutDeductionDirection(str, enum.Enum):
    ADD = "ADD"
    DEDUCT = "DEDUCT"


class FinancePayoutDeductionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REVERSED = "REVERSED"


class FinanceCorrectionProposal(Base):
    __tablename__ = "finance_correction_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    billing_month: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    client_invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("client_invoices.id"))
    therapist_invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"))
    proposal_type: Mapped[FinanceCorrectionProposalType] = mapped_column(
        Enum(FinanceCorrectionProposalType), nullable=False
    )
    wrong_side: Mapped[Optional[FinanceWrongSide]] = mapped_column(Enum(FinanceWrongSide))
    status: Mapped[FinanceProposalStatus] = mapped_column(
        Enum(FinanceProposalStatus), nullable=False, default=FinanceProposalStatus.PENDING
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    old_client_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    new_client_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    old_payout_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    new_payout_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    case_share_ratio: Mapped[Optional[float]] = mapped_column(Numeric(16, 8))
    record_correction_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class FinancePayoutDeduction(Base):
    __tablename__ = "finance_payout_deductions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    billing_month: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    therapist_invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"))
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    direction: Mapped[FinancePayoutDeductionDirection] = mapped_column(
        Enum(FinancePayoutDeductionDirection), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[CaseFinanceNoteType] = mapped_column(Enum(CaseFinanceNoteType), nullable=False)
    status: Mapped[FinancePayoutDeductionStatus] = mapped_column(
        Enum(FinancePayoutDeductionStatus), nullable=False, default=FinancePayoutDeductionStatus.ACTIVE
    )
    reversed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reversed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    reversal_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseFinanceNote(Base):
    __tablename__ = "case_finance_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    billing_month: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    note_scope: Mapped[CaseFinanceNoteScope] = mapped_column(Enum(CaseFinanceNoteScope), nullable=False)
    note_type: Mapped[CaseFinanceNoteType] = mapped_column(Enum(CaseFinanceNoteType), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    linked_deduction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("finance_payout_deductions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
