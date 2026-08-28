from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from typing import Optional

from sqlalchemy.orm import Session

from app.models.report import MonthlyReport, ObservationReport
from app.services.reports_export_helpers import parent_by_child, case_people_export_fields


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[str, str]] = []
        self._current_tag: Optional[str] = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("p", "h1", "h2", "h3", "li", "blockquote"):
            self._flush()
            self._current_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in ("p", "h1", "h2", "h3", "li", "blockquote", "div"):
            self._flush()

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._buffer.append(data)

    def _flush(self) -> None:
        if self._buffer:
            text = " ".join(self._buffer).strip()
            if text:
                self.blocks.append((self._current_tag or "p", text))
            self._buffer = []
            self._current_tag = None

    def finish(self) -> list[tuple[str, str]]:
        self._flush()
        return self.blocks


def _html_to_blocks(html: Optional[str]) -> list[tuple[str, str]]:
    if not html or not html.strip():
        return []
    parser = _HtmlTextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return [("p", text)] if text else []
    return parser.blocks or []


def _parent_display_name(
    db: Session | None = None,
    *,
    child_id: int | None = None,
    parent_name: Optional[str] = None,
) -> str:
    if parent_name:
        return parent_name.strip()
    if not db or not child_id:
        return ""
    info = parent_by_child(db, {child_id}).get(child_id)
    return case_people_export_fields(None, parent_info=info, include_therapist=False)["Parent Name"]


def build_report_pdf_bytes(
    *,
    title: str,
    child_name: str,
    case_code: str,
    category: Optional[str],
    month_label: str,
    body_html: Optional[str],
    plan_next_month: Optional[str],
    generated_by: Optional[str] = None,
    generated_at: Optional[str] = None,
    parent_name: Optional[str] = None,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=8,
        textColor=colors.HexColor("#1e293b"),
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontSize=11,
        leading=15,
        spaceAfter=8,
    )
    plan_style = ParagraphStyle(
        "ReportPlan",
        parent=styles["Normal"],
        fontSize=11,
        leading=15,
        backColor=colors.HexColor("#ecfdf5"),
        borderPadding=8,
        spaceBefore=12,
        spaceAfter=8,
    )

    meta_parts = [child_name, case_code, month_label]
    if parent_name:
        meta_parts = [child_name, parent_name, case_code, month_label]
    if category:
        meta_parts.append(category.replace("_", " ").title())
    story = [
        Paragraph(title, title_style),
        Paragraph(
            " · ".join(part for part in meta_parts if part),
            meta_style,
        ),
    ]

    blocks = _html_to_blocks(body_html)
    if not blocks:
        plain = re.sub(r"<[^>]+>", "", body_html or "").strip()
        if plain:
            blocks = [("p", plain)]

    for tag, text in blocks:
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if tag in ("h1", "h2", "h3"):
            story.append(Paragraph(f"<b>{safe}</b>", body_style))
        elif tag == "li":
            story.append(Paragraph(f"• {safe}", body_style))
        else:
            story.append(Paragraph(safe, body_style))

    if plan_next_month and plan_next_month.strip():
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>Plan for next month</b>", body_style))
        for line in plan_next_month.strip().split("\n"):
            if line.strip():
                safe = line.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe, plan_style))

    if generated_by or generated_at:
        story.append(Spacer(1, 20))
        parts = []
        if generated_by:
            parts.append(f"Generated by {generated_by.replace('&', '&amp;')}")
        if generated_at:
            parts.append(f"Generated at {generated_at.replace('&', '&amp;')}")
        story.append(Paragraph(" · ".join(parts), meta_style))

    doc.build(story)
    return buf.getvalue()


def monthly_report_pdf(
    report: MonthlyReport,
    case_code: str,
    child_name: str,
    *,
    generated_by: Optional[str] = None,
    generated_at: Optional[str] = None,
    parent_name: Optional[str] = None,
    db: Session | None = None,
    child_id: int | None = None,
) -> bytes:
    resolved_parent = _parent_display_name(db, child_id=child_id, parent_name=parent_name)
    return build_report_pdf_bytes(
        title=f"Monthly report — {report.month}",
        child_name=child_name,
        case_code=case_code,
        category=report.category,
        month_label=report.month,
        body_html=report.body_html or report.summary,
        plan_next_month=report.plan_next_month,
        generated_by=generated_by,
        generated_at=generated_at,
        parent_name=resolved_parent or None,
    )


def observation_report_pdf(
    report: ObservationReport,
    case_code: str,
    child_name: str,
    *,
    generated_by: Optional[str] = None,
    generated_at: Optional[str] = None,
    parent_name: Optional[str] = None,
    db: Session | None = None,
    child_id: int | None = None,
) -> bytes:
    resolved_parent = _parent_display_name(db, child_id=child_id, parent_name=parent_name)
    return build_report_pdf_bytes(
        title=report.title,
        child_name=child_name,
        case_code=case_code,
        category=report.category or "OBSERVATION",
        month_label="",
        body_html=report.body_html or report.content,
        plan_next_month=report.plan_next_month,
        generated_by=generated_by,
        generated_at=generated_at,
        parent_name=resolved_parent or None,
    )
