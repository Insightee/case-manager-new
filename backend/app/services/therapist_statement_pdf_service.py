"""Therapist monthly statement / payslip PDF (Insighte payout format)."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.services import invoice_billing_service

INSIGHTE_COMPANY = {
    "name": "Insighte Edutech Private Limited",
    "address": "No. 1, 1st Floor, 1st Main Road, Indiranagar, Bangalore - 560038",
    "email": "techsupport@insighte.org",
    "phone": "+91 63646 56234",
    "website": "www.insighte.org",
}

_STATUS_LABELS = {
    InvoiceStatus.DRAFT.value: "Draft",
    InvoiceStatus.IN_REVIEW.value: "In Review",
    InvoiceStatus.APPROVED.value: "Approved",
    InvoiceStatus.PAID.value: "Paid",
    InvoiceStatus.QUERIED.value: "Queried",
    InvoiceStatus.REJECTED.value: "Rejected",
}


def _employee_id(user: User) -> str:
    if user.external_employee_id:
        return str(user.external_employee_id)
    return str(user.id)


def _pref(user: User, key: str) -> str | None:
    prefs = user.ui_preferences if isinstance(user.ui_preferences, dict) else {}
    val = prefs.get(key)
    if val is None or str(val).strip() == "":
        return None
    return str(val).strip()


def _month_slug(month_label: str) -> str:
    """Apr 2026 -> july_2026 style slug for filenames."""
    try:
        dt = datetime.strptime(month_label.strip(), "%b %Y")
        return dt.strftime("%B_%Y").lower()
    except ValueError:
        return month_label.replace(" ", "_").lower()


def statement_pdf_filename(user: User, month_label: str) -> str:
    emp = _employee_id(user).replace(" ", "")
    return f"insighte_statement_{emp}_{_month_slug(month_label)}.pdf"


def _fmt_inr(amount: float | None) -> str:
    if amount is None:
        return "—"
    return f"₹{amount:,.0f}"


def build_statement_payload(db: Session, invoice: Invoice, therapist: User) -> dict[str, Any]:
    breakdown = invoice_billing_service.invoice_breakdown(db, invoice.id) or {}
    gross = float(breakdown.get("subtotal_inr") or invoice.subtotal_inr or invoice.amount_inr or 0)
    leave = float(breakdown.get("leave_deduction_inr") or invoice.leave_deduction_inr or 0)
    adjustment = float(breakdown.get("adjustment_inr") or invoice.adjustment_inr or 0)
    net = float(invoice.amount_inr or 0)
    sessions = int(breakdown.get("sessions_count") or invoice.sessions_count or 0)

    return {
        "statementNumber": f"STMT-{invoice.id:04d}",
        "monthLabel": invoice.month,
        "generatedAt": datetime.now(timezone.utc).strftime("%d %b %Y"),
        "status": _STATUS_LABELS.get(invoice.status.value, invoice.status.value),
        "therapistName": therapist.full_name,
        "employeeId": _employee_id(therapist),
        "designation": therapist.job_title or "Therapist",
        "pan": _pref(therapist, "pan") or "—",
        "bankAccount": _pref(therapist, "bank_account") or "—",
        "sessionsCount": sessions,
        "grossInr": round(gross, 2),
        "leaveDeductionInr": round(leave, 2),
        "adjustmentInr": round(adjustment, 2),
        "tdsInr": None,
        "holdbackInr": None,
        "netPayableInr": round(net, 2),
        "paidAmountInr": float(invoice.paid_amount_inr) if invoice.paid_amount_inr is not None else None,
        "paymentDate": invoice.updated_at.strftime("%d %b %Y") if invoice.status == InvoiceStatus.PAID else None,
        "paymentReference": f"PAY-{invoice.id:04d}" if invoice.status == InvoiceStatus.PAID else None,
        "company": INSIGHTE_COMPANY,
    }


def therapist_statement_pdf_bytes(payload: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    brand = colors.HexColor("#0f3d2e")
    muted = colors.HexColor("#64748b")
    title_style = ParagraphStyle("StmtTitle", parent=styles["Title"], fontSize=18, textColor=brand, spaceAfter=2)
    subtitle_style = ParagraphStyle("StmtSub", parent=styles["Normal"], fontSize=11, textColor=muted, spaceAfter=10)
    section_style = ParagraphStyle("StmtSection", parent=styles["Heading2"], fontSize=11, textColor=brand, spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle("StmtBody", parent=styles["Normal"], fontSize=10, leading=14)
    fine_style = ParagraphStyle("StmtFine", parent=styles["Normal"], fontSize=8, textColor=muted, leading=11)

    company = payload.get("company") or INSIGHTE_COMPANY
    story = [
        Paragraph(company["name"], title_style),
        Paragraph(
            f'{company["address"]}<br/>Email: {company["email"]} | Phone: {company["phone"]} | {company["website"]}',
            fine_style,
        ),
        Spacer(1, 14),
        Paragraph("Monthly Statement", ParagraphStyle("MainTitle", parent=title_style, fontSize=16)),
        Paragraph(
            f'Period: {payload.get("monthLabel", "")} &nbsp;|&nbsp; Statement No: {payload.get("statementNumber", "")} &nbsp;|&nbsp; Generated: {payload.get("generatedAt", "")}',
            subtitle_style,
        ),
        Paragraph("Employee Details", section_style),
    ]

    emp_rows = [
        ["Employee Name", payload.get("therapistName", "—"), "Employee ID", payload.get("employeeId", "—")],
        ["Designation", payload.get("designation", "—"), "PAN", payload.get("pan", "—")],
        ["Bank Account", payload.get("bankAccount", "—"), "Status", payload.get("status", "—")],
    ]
    emp_table = Table(emp_rows, colWidths=[95, 150, 95, 150])
    emp_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), brand),
                ("TEXTCOLOR", (2, 0), (2, -1), brand),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(emp_table)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Statement", section_style))

    def money_row(label: str, value: float | None, *, bold: bool = False) -> list:
        display = _fmt_inr(value) if value is not None else "Not yet configured"
        return [label, display]

    stmt_rows = [
        ["Description", "Amount"],
        ["Total Sessions", str(payload.get("sessionsCount") or 0)],
        money_row("Gross Amount", payload.get("grossInr")),
        money_row("TDS", payload.get("tdsInr")),
        money_row("Holdback", payload.get("holdbackInr")),
    ]
    leave_val = payload.get("leaveDeductionInr") or 0
    if leave_val > 0:
        stmt_rows.append(money_row("Leave Deduction", leave_val))
    adj = payload.get("adjustmentInr") or 0
    if adj != 0:
        stmt_rows.append(money_row("Adjustment", abs(adj)))
    stmt_rows.append(money_row("Net Payable", payload.get("netPayableInr"), bold=True))

    stmt_table = Table(stmt_rows, colWidths=[280, 210])
    stmt_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ecfdf5")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0fdf4")),
            ]
        )
    )
    story.append(stmt_table)

    if payload.get("status") == "Paid" and payload.get("paidAmountInr") is not None:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Payment Details", section_style))
        pay_rows = [
            ["Payment Date", payload.get("paymentDate") or "—"],
            ["Amount Paid", _fmt_inr(payload.get("paidAmountInr"))],
            ["Reference", payload.get("paymentReference") or "—"],
        ]
        pay_table = Table(pay_rows, colWidths=[120, 370])
        pay_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(pay_table)

    story.extend(
        [
            Spacer(1, 18),
            Paragraph(
                "This is a system-generated statement. For queries, contact techsupport@insighte.org",
                fine_style,
            ),
            Paragraph(f'© {datetime.now(timezone.utc).year} Insighte Edutech Private Limited. All rights reserved.', fine_style),
        ]
    )

    doc.build(story)
    return buf.getvalue()


def build_therapist_statement_pdf(db: Session, invoice: Invoice, therapist: User) -> tuple[bytes, str]:
    payload = build_statement_payload(db, invoice, therapist)
    content = therapist_statement_pdf_bytes(payload)
    filename = statement_pdf_filename(therapist, invoice.month)
    return content, filename
