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


def _button(href: str, label: str) -> str:
    safe_href = escape(href, quote=True)
    return (
        f'<p style="margin:24px 0;">'
        f'<a href="{safe_href}" style="display:inline-block;background:#2563eb;color:#ffffff;'
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
