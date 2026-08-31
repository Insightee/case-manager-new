"""Therapist monthly statement / payslip PDF (InsighteCase consolidated invoice)."""
from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.services import invoice_billing_service
from app.services import therapist_invoice_labels as labels

INSIGHTE_COMPANY = {
    "name": os.environ.get(
        "INVOICE_COMPANY_NAME",
        "Insighte Childcare Pvt Ltd",
    ),
    "address": os.environ.get(
        "INVOICE_COMPANY_ADDRESS",
        "#620, 1st Main, 1st Cross, AECS Layout, Bangalore - 560037",
    ),
    "email": os.environ.get("INVOICE_COMPANY_EMAIL", "techsupport@insighte.org"),
    "phone": os.environ.get("INVOICE_COMPANY_PHONE", "+91 63646 56234"),
    "website": os.environ.get("INVOICE_COMPANY_WEBSITE", "www.insighte.org"),
    "gstin": os.environ.get("INVOICE_COMPANY_GSTIN", ""),
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


def _is_homecare(case_group: dict) -> bool:
    mod = str(
        case_group.get("product_module")
        or (case_group.get("billing") or {}).get("product_module")
        or (case_group.get("billing_snapshot") or {}).get("product_module")
        or ""
    ).lower()
    return "homecare" in mod


def _collect_case_rows(case_group: dict) -> list[list[str]]:
    """Session-wise rows for one case."""
    rows: list[list[str]] = []

    def add(line: dict, *, force_pending: bool = False) -> None:
        date_s = str(line.get("session_date") or "")
        what = str(line.get("ui_label") or line.get("line_type") or "Session")
        tag = str(line.get("status_tag") or "")
        if force_pending or line.get("breakdown_bucket") == labels.BUCKET_PENDING or (line.get("flags") or {}).get(
            "pending_approval"
        ):
            tag = labels.PENDING_TAG
        amt = line.get("display_amount_inr")
        if amt is None:
            amt = line.get("amount_inr")
        in_pay = "Yes" if line.get("breakdown_bucket") == labels.BUCKET_IN_PAY and not force_pending else "No"
        if force_pending or line.get("breakdown_bucket") == labels.BUCKET_PENDING:
            in_pay = "Held"
        if line.get("breakdown_bucket") == labels.BUCKET_INFO:
            in_pay = "—"
        rows.append([date_s, what, tag, _fmt_inr(float(amt or 0)), in_pay])

    for line in case_group.get("session_lines") or []:
        if line.get("included") is False and not (line.get("flags") or {}).get("pending_approval"):
            continue
        add(line)
    for line in case_group.get("pending_approval_lines") or case_group.get("pending_late_lines") or []:
        add(line, force_pending=True)
    for line in case_group.get("child_absence_lines") or []:
        add(line)
    for line in case_group.get("leave_lines") or []:
        add(line)
    rows.sort(key=lambda r: r[0])
    return rows


def build_statement_payload(db: Session, invoice: Invoice, therapist: User) -> dict[str, Any]:
    breakdown = invoice_billing_service.invoice_breakdown(db, invoice.id) or {}
    gross = float(breakdown.get("subtotal_inr") or invoice.subtotal_inr or invoice.amount_inr or 0)
    leave = float(breakdown.get("leave_deduction_inr") or invoice.leave_deduction_inr or 0)
    adjustment = float(breakdown.get("adjustment_inr") or invoice.adjustment_inr or 0)
    tds = float(invoice.tds_inr) if invoice.tds_inr is not None else None
    net = float(invoice.net_payable_inr or invoice.amount_inr or 0)
    if tds is not None and invoice.net_payable_inr is None:
        net = max(gross - leave - tds + adjustment, 0)
    sessions = int(breakdown.get("sessions_count") or invoice.sessions_count or 0)
    leave_balance = breakdown.get("leave_balance")

    case_blocks = []
    for cg in breakdown.get("cases") or []:
        plan = cg.get("next_month_session_plan") or {}
        if isinstance(cg.get("billing_snapshot"), dict) and not plan:
            plan = cg["billing_snapshot"].get("next_month_session_plan") or {}
        case_blocks.append(
            {
                "caseCode": cg.get("case_code"),
                "childName": cg.get("child_name"),
                "homecare": _is_homecare(cg),
                "caseTotal": float(cg.get("therapist_share_inr") or 0),
                "rows": _collect_case_rows(cg),
                "nextMonthPlan": plan,
                "productModule": cg.get("product_module")
                or (cg.get("billing") or {}).get("product_module")
                or (cg.get("billing_snapshot") or {}).get("product_module"),
            }
        )

    return {
        "statementNumber": f"INV-{invoice.id:04d}",
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
        "tdsInr": round(tds, 2) if tds is not None else None,
        "holdbackInr": None,
        "netPayableInr": round(net, 2),
        "paidAmountInr": float(invoice.paid_amount_inr) if invoice.paid_amount_inr is not None else None,
        "paymentDate": invoice.updated_at.strftime("%d %b %Y") if invoice.status == InvoiceStatus.PAID else None,
        "paymentReference": f"PAY-{invoice.id:04d}" if invoice.status == InvoiceStatus.PAID else None,
        "company": INSIGHTE_COMPANY,
        "cases": case_blocks,
        "leaveBalance": leave_balance,
        "notes": invoice.notes,
    }


def therapist_statement_pdf_bytes(payload: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=42, rightMargin=42, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    brand = colors.HexColor("#0f3d2e")
    muted = colors.HexColor("#64748b")
    title_style = ParagraphStyle("StmtTitle", parent=styles["Title"], fontSize=18, textColor=brand, spaceAfter=2)
    subtitle_style = ParagraphStyle("StmtSub", parent=styles["Normal"], fontSize=10, textColor=muted, spaceAfter=8)
    section_style = ParagraphStyle(
        "StmtSection", parent=styles["Heading2"], fontSize=11, textColor=brand, spaceBefore=10, spaceAfter=4
    )
    body_style = ParagraphStyle("StmtBody", parent=styles["Normal"], fontSize=9, leading=12)
    fine_style = ParagraphStyle("StmtFine", parent=styles["Normal"], fontSize=8, textColor=muted, leading=11)

    company = payload.get("company") or INSIGHTE_COMPANY
    gst = company.get("gstin") or ""
    story = [
        Paragraph("INVOICE", title_style),
        Paragraph(company["name"], ParagraphStyle("Co", parent=body_style, fontSize=11, textColor=brand)),
        Paragraph(
            f'{company["address"]}<br/>Email: {company["email"]} | Phone: {company["phone"]} | {company["website"]}'
            + (f'<br/>GSTIN: {gst}' if gst else ""),
            fine_style,
        ),
        Spacer(1, 10),
        Paragraph(
            f'Period: {payload.get("monthLabel", "")} &nbsp;|&nbsp; Invoice No: {payload.get("statementNumber", "")} '
            f'&nbsp;|&nbsp; Generated: {payload.get("generatedAt", "")}',
            subtitle_style,
        ),
        Paragraph("Bill From / Bill To", section_style),
    ]

    emp_rows = [
        ["Bill From", payload.get("therapistName", "—"), "Bill To", company["name"]],
        ["Employee ID", payload.get("employeeId", "—"), "Address", company["address"]],
        ["PAN", payload.get("pan", "—"), "Status", payload.get("status", "—")],
        ["Bank Account", payload.get("bankAccount", "—"), "Designation", payload.get("designation", "—")],
    ]
    emp_table = Table(emp_rows, colWidths=[85, 160, 85, 160])
    emp_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (0, -1), brand),
                ("TEXTCOLOR", (2, 0), (2, -1), brand),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(emp_table)

    for block in payload.get("cases") or []:
        title = f'{block.get("caseCode") or "Case"}'
        if block.get("childName"):
            title += f' · {block["childName"]}'
        title += " · Homecare" if block.get("homecare") else " · Shadow"
        story.append(Paragraph(title, section_style))
        if block.get("homecare"):
            story.append(
                Paragraph(
                    "Homecare pay is based on sessions completed. Leave and child away are cancelled — not billed.",
                    fine_style,
                )
            )
        else:
            story.append(
                Paragraph(
                    "Shadow monthly share: child away and paid leave stay paid; unpaid leave is deducted.",
                    fine_style,
                )
            )
        table_data = [["Date", "What happened", "Tag", "Amount", "In this pay?"]]
        table_data.extend(block.get("rows") or [["—", "No session lines", "", "", ""]])
        t = Table(table_data, colWidths=[70, 180, 90, 60, 70])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ecfdf5")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                    ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(t)
        story.append(Paragraph(f'Case total: {_fmt_inr(block.get("caseTotal"))}', body_style))

        plan = block.get("nextMonthPlan") or {}
        plan_sessions = plan.get("sessions") if isinstance(plan, dict) else None
        if plan_sessions:
            story.append(Paragraph("Next month session plan (not billed this month)", fine_style))
            for s in plan_sessions:
                story.append(
                    Paragraph(
                        f'• {s.get("date", "")} {s.get("start_time") or ""}'
                        f'{("–" + s["end_time"]) if s.get("end_time") else ""}'
                        f'{(" · " + s["note"]) if s.get("note") else ""}',
                        fine_style,
                    )
                )

    lb = payload.get("leaveBalance")
    if lb:
        story.append(Paragraph("Leave credits", section_style))
        story.append(
            Paragraph(
                f'Year {lb.get("year")}: earned {lb.get("credits_earned", "—")} · '
                f'used {lb.get("paid_leaves_taken") or lb.get("paid_used_effective") or 0} · '
                f'remaining {lb.get("leave_credit_pending") or lb.get("paid_remaining") or 0}. '
                f'Resets each January.',
                body_style,
            )
        )

    story.append(Paragraph("Statement totals", section_style))

    def money_row(label: str, value: float | None) -> list:
        display = _fmt_inr(value) if value is not None else "—"
        return [label, display]

    stmt_rows = [
        ["Description", "Amount"],
        ["Sessions in this pay", str(payload.get("sessionsCount") or 0)],
        money_row("Gross Amount", payload.get("grossInr")),
    ]
    leave_val = payload.get("leaveDeductionInr") or 0
    if leave_val > 0:
        stmt_rows.append(money_row("Unpaid leave adjustment", leave_val))
    stmt_rows.append(money_row("TDS", payload.get("tdsInr")))
    adj = payload.get("adjustmentInr") or 0
    if adj != 0:
        stmt_rows.append(money_row("Adjustment", abs(adj)))
    stmt_rows.append(money_row("Net Payable", payload.get("netPayableInr")))

    stmt_table = Table(stmt_rows, colWidths=[300, 190])
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

    if payload.get("notes"):
        story.append(Spacer(1, 8))
        story.append(Paragraph("Remarks", section_style))
        story.append(Paragraph(str(payload["notes"]).replace("\n", "<br/>"), body_style))

    if payload.get("status") == "Paid" and payload.get("paidAmountInr") is not None:
        story.append(Spacer(1, 10))
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
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(pay_table)

    story.extend(
        [
            Spacer(1, 16),
            Paragraph(
                "This document is generated by InsighteCase. For queries, contact techsupport@insighte.org",
                fine_style,
            ),
            Paragraph(
                f'© {datetime.now(timezone.utc).year} {company["name"]}. All rights reserved.',
                fine_style,
            ),
        ]
    )

    doc.build(story)
    return buf.getvalue()


def build_therapist_statement_pdf(db: Session, invoice: Invoice, therapist: User) -> tuple[bytes, str]:
    payload = build_statement_payload(db, invoice, therapist)
    content = therapist_statement_pdf_bytes(payload)
    filename = statement_pdf_filename(therapist, invoice.month)
    return content, filename
