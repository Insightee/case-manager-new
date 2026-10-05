/** Detect stale PWA / cached bundle issues after deploys (field therapists & parents). */

export const PWA_STALE_HINT_KEY = 'insightcase:pwa-stale-hint'

const STALE_MESSAGE_FRAGMENTS = [
  'failed to fetch dynamically imported module',
  'error loading dynamically imported module',
  'importing a module script failed',
  'failed to load module script',
  'load failed',
  'dynamically imported module',
  'chunkloaderror',
]

export function markPwaStaleHint() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(PWA_STALE_HINT_KEY, String(Date.now()))
}

export function hasPwaStaleHint() {
  if (typeof sessionStorage === 'undefined') return false
  return Boolean(sessionStorage.getItem(PWA_STALE_HINT_KEY))
}

export function clearPwaStaleHint() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.removeItem(PWA_STALE_HINT_KEY)
}

/** @param {unknown} err */
export function isLikelyStaleAppError(err) {
  const msg = String(err?.message || err || '').toLowerCase()
  if (err?.name === 'ChunkLoadError') return true
  return STALE_MESSAGE_FRAGMENTS.some((fragment) => msg.includes(fragment))
}

/**
 * Login failures in a home-screen app are often a stale bundle, not bad passwords.
 * @param {unknown} err
 * @param {{ standalone?: boolean }} [opts]
 */
export function isLikelyStaleLoginFailure(err, opts = {}) {
  if (!opts.standalone) return false
  const msg = String(err?.message || err || '').toLowerCase()
  if (msg.includes('invalid credentials')) return false
  if (msg.includes('invalid login')) return false
  if (msg.includes('use the correct portal')) return false
  if (isLikelyStaleAppError(err)) return true
  if (/failed to fetch|network|load failed|timed out|unexpected token|<!doctype/i.test(msg)) return true
  return false
}

export function portalUrlForBrowser() {
  if (typeof window === 'undefined') return ''
  return window.location.href
}

export async function copyPortalUrlForBrowser() {
  const url = portalUrlForBrowser()
  if (!url) return { ok: false }
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(url)
      return { ok: true, url }
    }
  } catch {
    // fall through
  }
  return { ok: false, url }
}
