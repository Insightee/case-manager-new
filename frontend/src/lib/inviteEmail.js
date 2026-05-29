/** User-facing copy for portal invite email delivery status from the API. */
export function inviteEmailMessage(email, delivery) {
  const base = `Invite link generated for ${email}.`
  if (delivery === 'queued' || delivery === 'sent_sync') {
    return `${base} Check the inbox (and spam) for the portal invite.`
  }
  if (delivery === 'skipped_no_smtp') {
    return `${base} Email was not sent — SMTP is not configured on the API server. Copy the link or use Resend email after SMTP is set.`
  }
  if (delivery === 'skipped_disabled') {
    return `${base} Email sending was turned off for this invite.`
  }
  return base
}
