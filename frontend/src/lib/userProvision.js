/** Messages for activate-for-login / invite-to-login API results. */

function roleLabel(role) {
  if (!role) return 'user'
  return String(role).replace(/_/g, ' ')
}

export function formatInviteStatus(status) {
  if (!status || status === 'none') return 'No invite'
  if (status === 'pending') return 'Invite pending'
  if (status === 'used') return 'Invite used'
  if (status === 'expired') return 'Invite expired'
  return status
}

export function formatLoginReady(loginReady, userActive) {
  if (loginReady) return 'Login ready'
  if (!userActive) return 'Inactive'
  return 'Needs password'
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
  if (res?.invite_sent) {
    return `Login email queued for ${email} (${role}).`
  }
  if (res?.invite_error === 'smtp_not_configured') {
    return `Invite link ready for ${email} (${role}). Email was not sent — SMTP is not configured. Copy the link below.`
  }
  if (res?.invite_error) {
    return `Invite link ready for ${email} (${role}). Email was not sent (${res.invite_error}). Copy the link if needed.`
  }
  return `Invite prepared for ${email} (${role}).`
}

export function provisionInviteFailure(res) {
  if (!res?.invite_sent && res?.invite_error) {
    return `Invite email for ${res.email || 'user'} was not sent: ${res.invite_error}`
  }
  return null
}
