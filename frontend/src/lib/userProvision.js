/** Messages for activate-for-login / invite-to-login API results. */

function roleLabel(role) {
  if (!role) return 'user'
  return String(role).replace(/_/g, ' ')
}

function formatTimestamp(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export function formatInviteStatus(status) {
  if (!status || status === 'none') return 'No invite'
  if (status === 'pending') return 'Invite pending'
  if (status === 'used') return 'Invite used'
  if (status === 'expired') return 'Invite expired'
  if (status === 'delivery_failed') return 'Delivery failed'
  return status
}

export function formatEmailDeliveryStatus(status, user) {
  if (user?.is_email_suppressed) {
    const reason = user.suppression_reason ? ` (${user.suppression_reason})` : ''
    return `Email blocked${reason}`
  }
  if (!status || status === 'not_sent') return null
  if (status === 'accepted' || status === 'sent') return 'Email accepted by provider'
  if (status === 'delivered') return 'Delivered'
  if (status === 'failed_retrying') return 'Send failed — retry scheduled'
  if (status === 'failed_final') return 'Delivery failed (max attempts)'
  if (status === 'hard_bounced') return 'Hard bounce — fix email address'
  if (status === 'suppressed') return 'Email suppressed'
  if (status.startsWith('skipped_')) return 'Send skipped'
  return status.replace(/_/g, ' ')
}

export function formatLoginReady(loginReady, userActive) {
  if (loginReady) return 'Login ready'
  if (!userActive) return 'Inactive'
  return 'Needs password'
}

export function inviteResendBlocked(user) {
  if (user?.is_email_suppressed) {
    return 'Email is blocked due to a bounce. Correct the address and clear suppression before resending.'
  }
  const status = user?.email_delivery_status
  if (status === 'failed_final' || user?.invite_status === 'delivery_failed') {
    return 'Delivery failed after 3 attempts. Verify the email, then use force resend.'
  }
  if (user?.resend_allowed_at) {
    const allowed = new Date(user.resend_allowed_at)
    if (!Number.isNaN(allowed.getTime()) && allowed > new Date()) {
      return `Resend available after ${formatTimestamp(user.resend_allowed_at)}.`
    }
  }
  return null
}

export function provisionActivateSuccess(res) {
  const email = res?.email || 'user'
  const role = roleLabel(res?.role)
  if (res?.login_ready) {
    return `${email} (${role}) is active and can sign in.`
  }
  if (res?.user_active) {
    return `${email} (${role}) is active. Set a password or send an invite so they can sign in.`
  }
  return `Could not activate ${email}.`
}

export function provisionInviteSuccess(res) {
  const email = res?.email || 'user'
  const role = roleLabel(res?.role)
  if (res?.delivery_message && !res?.invite_sent) {
    return res.delivery_message
  }
  if (res?.invite_sent) {
    const delivery = formatEmailDeliveryStatus(res.email_delivery_status, res)
    if (delivery) return `Login email queued for ${email} (${role}). ${delivery}.`
    return `Login email queued for ${email} (${role}).`
  }
  if (res?.invite_error === 'smtp_not_configured') {
    return `Invite link ready for ${email} (${role}). Email was not sent — SMTP is not configured. Copy the link below.`
  }
  if (res?.invite_error === 'cooldown_or_duplicate') {
    const when = formatTimestamp(res.resend_allowed_at)
    return when
      ? `Invite already sent to ${email}. You can resend after ${when}.`
      : `Invite already sent to ${email}. Please wait before resending.`
  }
  if (res?.invite_error) {
    return `Invite link ready for ${email} (${role}). Email was not sent (${res.invite_error}). Copy the link if needed.`
  }
  return `Invite prepared for ${email} (${role}).`
}

export function provisionInviteFailure(res) {
  if (res?.delivery_message && !res?.invite_sent) {
    return res.delivery_message
  }
  if (res?.is_email_suppressed) {
    return `Email for ${res.email || 'user'} is blocked. Correct the address before resending.`
  }
  if (!res?.invite_sent && res?.invite_error && res.invite_error !== 'cooldown_or_duplicate') {
    return `Invite email for ${res.email || 'user'} was not sent: ${res.invite_error}`
  }
  return null
}

export function inviteRowResendHint(invite) {
  if (invite?.expired_due_to_delivery_failure) {
    return 'Delivery failed. Correct the email and use force resend.'
  }
  if (invite?.resend_allowed_at) {
    const allowed = new Date(invite.resend_allowed_at)
    if (!Number.isNaN(allowed.getTime()) && allowed > new Date()) {
      return `Cooldown until ${formatTimestamp(invite.resend_allowed_at)}`
    }
  }
  const status = invite?.email_delivery_status
  if (status === 'failed_final' || status === 'hard_bounced') {
    return 'Fix the email address before resending.'
  }
  return null
}
