export const FORGOT_PASSWORD_COOLDOWN_SECONDS = 30
export const FORGOT_PASSWORD_COOLDOWN_KEY = 'insighte_forgot_password_cooldown_until'

export function readForgotPasswordCooldownRemaining(now = Date.now()) {
  if (typeof sessionStorage === 'undefined') return 0
  const untilRaw = sessionStorage.getItem(FORGOT_PASSWORD_COOLDOWN_KEY)
  if (!untilRaw) return 0
  const until = Number(untilRaw)
  if (!Number.isFinite(until)) {
    sessionStorage.removeItem(FORGOT_PASSWORD_COOLDOWN_KEY)
    return 0
  }
  const remaining = Math.ceil((until - now) / 1000)
  if (remaining <= 0) {
    sessionStorage.removeItem(FORGOT_PASSWORD_COOLDOWN_KEY)
    return 0
  }
  return remaining
}

export function startForgotPasswordCooldown(now = Date.now()) {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(
    FORGOT_PASSWORD_COOLDOWN_KEY,
    String(now + FORGOT_PASSWORD_COOLDOWN_SECONDS * 1000),
  )
}

export function clearForgotPasswordCooldown() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.removeItem(FORGOT_PASSWORD_COOLDOWN_KEY)
}
