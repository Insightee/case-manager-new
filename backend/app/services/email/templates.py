from __future__ import annotations

from html import escape
from typing import Any

BRAND_NAME = "Insighte"


def _layout(*, title: str, body_html: str, locale: str = "en") -> str:
    _ = locale
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:8px;overflow:hidden;">
          <tr>
            <td style="background:#1e3a5f;padding:20px 24px;">
              <p style="margin:0;color:#ffffff;font-size:20px;font-weight:600;">{BRAND_NAME}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:24px;color:#1a1a1a;font-size:16px;line-height:1.5;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:16px 24px 24px;border-top:1px solid #e8ecf0;color:#6b7280;font-size:13px;line-height:1.4;">
              This message was sent by {BRAND_NAME}. If you did not expect it, you can ignore this email.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _button(href: str, label: str, *, variant: str = "primary") -> str:
    safe_href = escape(href, quote=True)
    if variant == "calendar":
        bg, color = "#1a73e8", "#ffffff"
        margin = "margin:12px 0 0 0;"
    else:
        bg, color = "#2563eb", "#ffffff"
        margin = "margin:24px 0;"
    return (
        f'<p style="{margin}">'
        f'<a href="{safe_href}" style="display:inline-block;background:{bg};color:{color};'
        f'text-decoration:none;padding:12px 20px;border-radius:6px;font-weight:600;">'
        f"{escape(label)}</a></p>"
    )


def render_template(template_key: str, payload: dict[str, Any], *, locale: str = "en") -> tuple[str, str, str]:
    """Return (subject, text_body, html_body)."""
    renderers = {
        "password_reset": _password_reset,
        "portal_invite": _portal_invite,
        "invoice_generated": _invoice_generated,
        "report_uploaded": _report_uploaded,
        "report_published": _report_published,
        "payment_reminder": _payment_reminder,
        "cm_meeting_invite": _cm_meeting_invite,
    }
    fn = renderers.get(template_key)
    if not fn:
        subject = payload.get("subject", "Notification from Insighte")
        text = payload.get("body_text", str(payload))
        html = _layout(title=subject, body_html=f"<p>{escape(text)}</p>", locale=locale)
        return subject, text, html
    return fn(payload, locale=locale)


def _portal_invite(payload: dict[str, Any], *, locale: str = "en") -> tuple[str, str, str]:
    full_name = payload.get("full_name", "there")
    invite_url = payload.get("invite_url", "")
    role_label = payload.get("role_label", "team member")
    intro_line = payload.get("intro_line", f"You have been invited to join Insighte as a {role_label}.")
    subject = f"You're invited to Insighte — {role_label}"
    text = (
        f"Hi {full_name},\n\n"
        f"{intro_line}\n\n"
        f"Create your account here:\n{invite_url}\n\n"
        "This link expires in 7 days. If you did not expect this, you can ignore this email.\n"
    )
    body = (
        f"<p>Hi {escape(str(full_name))},</p>"
        f"<p>{escape(str(intro_line))}</p>"
        f"{_button(invite_url, 'Accept invitation')}"
        f'<p style="color:#6b7280;font-size:14px;">This link expires in 7 days.</p>'
        f"<p>If you did not expect this, you can ignore this email.</p>"
    )
    html = _layout(title=subject, body_html=body, locale=locale)
    return subject, text, html


def _password_reset(payload: dict[str, Any], *, locale: str = "en") -> tuple[str, str, str]:
    full_name = payload.get("full_name", "there")
    reset_url = payload.get("reset_url", "")
    expires_hours = int(payload.get("expires_hours", 1))
    subject = "Reset your Insighte password"
    text = (
        f"Hi {full_name},\n\n"
        "We received a request to reset your password.\n\n"
        f"Reset your password here (link expires in {expires_hours} hour(s)):\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    body = (
        f"<p>Hi {escape(str(full_name))},</p>"
        f"<p>We received a request to reset your Insighte password.</p>"
        f"{_button(reset_url, 'Reset password')}"
        f'<p style="color:#6b7280;font-size:14px;">This link expires in {expires_hours} hour(s).</p>'
        f"<p>If you did not request this, you can ignore this email.</p>"
    )
    html = _layout(title=subject, body_html=body, locale=locale)
    return subject, text, html


def _invoice_generated(payload: dict[str, Any], *, locale: str = "en") -> tuple[str, str, str]:
    parent_name = payload.get("parent_name", "there")
    invoice_number = payload.get("invoice_number", "")
    child_name = payload.get("child_name", "your child")
    total_inr = float(payload.get("total_inr", 0))
    balance_inr = float(payload.get("balance_inr", 0))
    due_date_str = payload.get("due_date_str")
    is_overdue = bool(payload.get("is_overdue"))
    payments_url = payload.get("payments_url", "")
    due_line = f"Due date: {due_date_str}.\n" if due_date_str else ""
    overdue_line = "This invoice is overdue — please pay as soon as you can.\n" if is_overdue else ""
    subject = (
        f"Invoice {invoice_number} — action needed"
        if balance_inr > 0
        else f"Invoice {invoice_number} — Insighte"
    )
    text = (
        f"Hi {parent_name},\n\n"
        f"A new invoice is ready in your client portal.\n\n"
        f"Invoice: {invoice_number}\n"
        f"For: {child_name}\n"
        f"Amount: ₹{total_inr:,.0f} (balance due: ₹{balance_inr:,.0f})\n"
        f"{due_line}{overdue_line}\n"
        f"View and pay: {payments_url}\n"
    )
    overdue_html = (
        '<p style="color:#b45309;font-weight:600;">This invoice is overdue — please pay as soon as you can.</p>'
        if is_overdue
        else ""
    )
    due_html = f"<p><strong>Due date:</strong> {escape(str(due_date_str))}</p>" if due_date_str else ""
    body = (
        f"<p>Hi {escape(str(parent_name))},</p>"
        f"<p>A new invoice is ready in your client portal.</p>"
        f"<p><strong>Invoice:</strong> {escape(str(invoice_number))}<br/>"
        f"<strong>For:</strong> {escape(str(child_name))}<br/>"
        f"<strong>Amount:</strong> ₹{total_inr:,.0f} (balance due: ₹{balance_inr:,.0f})</p>"
        f"{due_html}{overdue_html}"
        f"{_button(payments_url, 'View invoice')}"
    )
    html = _layout(title=subject, body_html=body, locale=locale)
    return subject, text, html


def _report_uploaded(payload: dict[str, Any], *, locale: str = "en") -> tuple[str, str, str]:
    parent_name = payload.get("parent_name", "there")
    child_name = payload.get("child_name", "your child")
    report_label = payload.get("report_label", "Monthly report")
    portal_url = payload.get("portal_url", "")
    subject = f"Report update — {child_name}"
    text = (
        f"Hi {parent_name},\n\n"
        f"A report for {child_name} ({report_label}) was submitted and is being reviewed.\n\n"
        f"Portal: {portal_url}\n"
    )
    body = (
        f"<p>Hi {escape(str(parent_name))},</p>"
        f"<p>A report for <strong>{escape(str(child_name))}</strong> ({escape(str(report_label))}) "
        f"was submitted and is being reviewed.</p>"
        f"{_button(portal_url, 'Open portal') if portal_url else ''}"
    )
    html = _layout(title=subject, body_html=body, locale=locale)
    return subject, text, html


def _report_published(payload: dict[str, Any], *, locale: str = "en") -> tuple[str, str, str]:
    parent_name = payload.get("parent_name", "there")
    child_name = payload.get("child_name", "your child")
    report_label = payload.get("report_label", "Monthly report")
    portal_url = payload.get("portal_url", "")
    subject = f"New report available — {child_name}"
    text = (
        f"Hi {parent_name},\n\n"
        f"The {report_label} for {child_name} is now available in your portal.\n\n"
        f"View it here: {portal_url}\n"
    )
    body = (
        f"<p>Hi {escape(str(parent_name))},</p>"
        f"<p>The <strong>{escape(str(report_label))}</strong> for "
        f"<strong>{escape(str(child_name))}</strong> is now available.</p>"
        f"{_button(portal_url, 'View report')}"
    )
    html = _layout(title=subject, body_html=body, locale=locale)
    return subject, text, html


def _cm_meeting_invite(payload: dict[str, Any], *, locale: str = "en") -> tuple[str, str, str]:
    full_name = payload.get("full_name", "there")
    meeting_title = payload.get("meeting_title", "Case manager meeting")
    when = payload.get("when", "")
    duration_minutes = int(payload.get("duration_minutes", 30))
    child_name = payload.get("child_name")
    case_code = payload.get("case_code")
    organizer_name = payload.get("organizer_name", "Insighte")
    meeting_url = (payload.get("meeting_url") or "").strip()
    portal_url = (payload.get("portal_url") or "").strip()
    google_calendar_url = (payload.get("google_calendar_url") or "").strip()
    is_update = bool(payload.get("is_update"))

    case_line = ""
    if child_name or case_code:
        parts = [p for p in [child_name, f"({case_code})" if case_code else None] if p]
        case_line = " · ".join(parts)

    subject_prefix = "Updated: " if is_update else ""
    subject = f"{subject_prefix}Meeting invitation — {meeting_title}"

    when_block = f"When: {when}\nDuration: {duration_minutes} minutes\n" if when else ""
    case_block = f"Case: {case_line}\n" if case_line else ""
    link_block = f"Join meeting:\n{meeting_url}\n\n" if meeting_url else ""
    calendar_block = (
        f"Add to Google Calendar:\n{google_calendar_url}\n\n" if google_calendar_url else ""
    )
    portal_block = f"View in Insighte:\n{portal_url}\n\n" if portal_url else ""

    text = (
        f"Hi {full_name},\n\n"
        f"{'This meeting was updated. ' if is_update else ''}"
        f"{organizer_name} invited you to a case manager meeting.\n\n"
        f"Meeting: {meeting_title}\n"
        f"{case_block}"
        f"{when_block}"
        f"{link_block}"
        f"{calendar_block}"
        f"{portal_block}"
        "You will also see this meeting in your Insighte notifications.\n"
    )

    case_html = (
        f"<p><strong>Case:</strong> {escape(case_line)}</p>" if case_line else ""
    )
    when_html = (
        f"<p><strong>When:</strong> {escape(str(when))}<br/>"
        f"<strong>Duration:</strong> {duration_minutes} minutes</p>"
        if when
        else ""
    )
    update_html = (
        '<p style="color:#b45309;font-weight:600;">This meeting was updated.</p>'
        if is_update
        else ""
    )
    link_html = _button(meeting_url, "Join meeting") if meeting_url else ""
    calendar_html = (
        _button(google_calendar_url, "Add to Google Calendar", variant="calendar")
        if google_calendar_url
        else ""
    )
    portal_html = (
        f'<p style="margin-top:16px;"><a href="{escape(portal_url, quote=True)}" '
        f'style="color:#2563eb;">Open meeting in Insighte</a></p>'
        if portal_url
        else ""
    )
    body = (
        f"<p>Hi {escape(str(full_name))},</p>"
        f"{update_html}"
        f"<p><strong>{escape(str(organizer_name))}</strong> invited you to "
        f"<strong>{escape(str(meeting_title))}</strong>.</p>"
        f"{case_html}{when_html}"
        f"{link_html}{calendar_html}{portal_html}"
        '<p style="color:#6b7280;font-size:14px;">You will also see this in your Insighte notifications.</p>'
    )
    html = _layout(title=subject, body_html=body, locale=locale)
    return subject, text, html


def _payment_reminder(payload: dict[str, Any], *, locale: str = "en") -> tuple[str, str, str]:
    parent_name = payload.get("parent_name", "there")
    invoice_number = payload.get("invoice_number", "")
    balance_inr = float(payload.get("balance_inr", 0))
    payments_url = payload.get("payments_url", "")
    subject = f"Payment reminder — invoice {invoice_number}"
    text = (
        f"Hi {parent_name},\n\n"
        f"This is a reminder that ₹{balance_inr:,.0f} is outstanding on invoice {invoice_number}.\n\n"
        f"Pay or review: {payments_url}\n"
    )
    body = (
        f"<p>Hi {escape(str(parent_name))},</p>"
        f"<p>This is a friendly reminder that <strong>₹{balance_inr:,.0f}</strong> is outstanding "
        f"on invoice <strong>{escape(str(invoice_number))}</strong>.</p>"
        f"{_button(payments_url, 'View invoice')}"
    )
    html = _layout(title=subject, body_html=body, locale=locale)
    return subject, text, html
