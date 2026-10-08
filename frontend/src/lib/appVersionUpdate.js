/** Build / service-worker version detection for PWA update prompts (all portals). */

import { isIosSafari, isStandaloneDisplay } from './portalPwa.js'

export const VERSION_DISMISS_KEY = 'insightcase:version-notice-dismissed'
export const VERSION_REFRESH_ATTEMPTS_KEY = 'insightcase:version-refresh-attempts'
export const SW_UPDATE_WAITING_KEY = 'insightcase:sw-update-waiting'
export const VERSION_CHECK_TS_KEY = 'insightcase:version-last-check'
export const HARD_RECOVERY_SHOWN_KEY = 'insightcase:version-hard-shown'

const MIN_CHECK_INTERVAL_MS = 5 * 60 * 1000
const MAX_SOFT_REFRESH_ATTEMPTS = 2

/** @returns {string} */
export function getEmbeddedBuildId() {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_BUILD_ID) {
    return String(import.meta.env.VITE_BUILD_ID)
  }
  return 'dev'
}

export function shouldPollRemoteVersion() {
  return Boolean(import.meta.env?.PROD)
}

/**
 * @param {string} embedded
 * @param {string | null | undefined} remote
 */
export function isRemoteBuildNewer(embedded, remote) {
  if (!remote || !embedded) return false
  if (embedded === 'dev' || remote === 'dev') return false
  return embedded !== remote
}

/** @param {unknown} err */
export function isGenericNetworkError(err) {
  const msg = String(err?.message || err || '').toLowerCase().trim()
  if (!msg) return false
  if (msg === 'load failed' || msg === 'error: load failed') return true
  if (msg === 'failed to fetch' || msg === 'networkerror when attempting to fetch resource.') return true
  if (msg.includes('network request failed')) return true
  return false
}

/**
 * @param {'ios' | 'android' | 'other'} platform
 * @param {{ portalUrl: string, appName: string }} ctx
 */
export function getReinstallSteps(platform, { portalUrl, appName }) {
  const url = portalUrl || 'your portal link'
  if (platform === 'ios') {
    return [
      `Press and hold the ${appName} icon on your home screen and choose Remove App, then Delete from Home Screen.`,
      `Open ${url} in Safari.`,
      'Tap the Share button, then Add to Home Screen.',
    ]
  }
  if (platform === 'android') {
    return [
      `Press and hold the ${appName} icon and choose Uninstall or Remove.`,
      `Open ${url} in Chrome.`,
      'Tap the ⋮ menu, then Install app or Add to Home screen.',
    ]
  }
  return [
    `Remove the old ${appName} shortcut from your home screen or dock.`,
    `Open ${url} in your browser.`,
    'Add the portal to your home screen again from the browser menu.',
  ]
}

/** @param {string} [userAgent] */
export function detectReinstallPlatform(userAgent = '') {
  const ua = userAgent || (typeof navigator !== 'undefined' ? navigator.userAgent : '')
  const isIos =
    /iPad|iPhone|iPod/.test(ua) ||
    (typeof navigator !== 'undefined' &&
      navigator.platform === 'MacIntel' &&
      navigator.maxTouchPoints > 1)
  if (isIos) return 'ios'
  if (/Android/i.test(ua)) return 'android'
  return 'other'
}

export function markServiceWorkerUpdateWaiting() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(SW_UPDATE_WAITING_KEY, String(Date.now()))
}

export function hasServiceWorkerUpdateWaiting() {
  if (typeof sessionStorage === 'undefined') return false
  return Boolean(sessionStorage.getItem(SW_UPDATE_WAITING_KEY))
}

export function clearServiceWorkerUpdateWaiting() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.removeItem(SW_UPDATE_WAITING_KEY)
}

export function getRefreshAttemptCount() {
  if (typeof sessionStorage === 'undefined') return 0
  const raw = sessionStorage.getItem(VERSION_REFRESH_ATTEMPTS_KEY)
  const n = Number(raw)
  return Number.isFinite(n) ? n : 0
}

export function recordRefreshAttempt() {
  if (typeof sessionStorage === 'undefined') return 0
  const next = getRefreshAttemptCount() + 1
  sessionStorage.setItem(VERSION_REFRESH_ATTEMPTS_KEY, String(next))
  return next
}

export function dismissVersionNoticeForSession(buildId) {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(VERSION_DISMISS_KEY, buildId || 'unknown')
}

export function isVersionNoticeDismissed(buildId) {
  if (typeof sessionStorage === 'undefined') return false
  const dismissed = sessionStorage.getItem(VERSION_DISMISS_KEY)
  return dismissed && buildId && dismissed === buildId
}

export function markHardRecoveryShown() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(HARD_RECOVERY_SHOWN_KEY, '1')
}

export function wasHardRecoveryShown() {
  if (typeof sessionStorage === 'undefined') return false
  return sessionStorage.getItem(HARD_RECOVERY_SHOWN_KEY) === '1'
}

export function canCheckVersionNow() {
  if (typeof sessionStorage === 'undefined') return true
  const raw = sessionStorage.getItem(VERSION_CHECK_TS_KEY)
  if (!raw) return true
  const last = Number(raw)
  if (!Number.isFinite(last)) return true
  return Date.now() - last >= MIN_CHECK_INTERVAL_MS
}

export function markVersionChecked() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(VERSION_CHECK_TS_KEY, String(Date.now()))
}

/**
 * Whether to show any update / stale UI (banner or sheet).
 * @param {{
 *   embeddedBuildId: string
 *   remoteBuildId?: string | null
 *   chunkStale?: boolean
 *   swWaiting?: boolean
 *   standalone?: boolean
 * }} input
 */
export function shouldShowVersionNotice(input) {
  const {
    embeddedBuildId,
    remoteBuildId = null,
    chunkStale = false,
    swWaiting = false,
    standalone = isStandaloneDisplay(),
  } = input

  const remoteNewer = isRemoteBuildNewer(embeddedBuildId, remoteBuildId)
  const buildKey = remoteBuildId || embeddedBuildId || 'unknown'

  if (!chunkStale && !swWaiting && !remoteNewer) return { show: false, mode: 'none', buildKey }

  if (isVersionNoticeDismissed(buildKey) && !chunkStale) {
    return { show: false, mode: 'none', buildKey }
  }

  const refreshAttempts = getRefreshAttemptCount()
  const hardEligible =
    standalone &&
    (chunkStale || remoteNewer || swWaiting) &&
    refreshAttempts >= MAX_SOFT_REFRESH_ATTEMPTS &&
    !wasHardRecoveryShown()

  if (hardEligible) {
    return { show: true, mode: 'hard', buildKey }
  }

  if (chunkStale || swWaiting || remoteNewer) {
    return { show: true, mode: 'soft', buildKey }
  }

  return { show: false, mode: 'none', buildKey }
}

/**
 * Fetch /version.json (cache-busted lightly).
 * @returns {Promise<{ buildId: string } | null>}
 */
export async function fetchRemoteVersionMeta() {
  if (!shouldPollRemoteVersion()) return null
  if (!canCheckVersionNow()) return null
  markVersionChecked()
  const url = `/version.json?t=${Date.now()}`
  try {
    const res = await fetch(url, { cache: 'no-store', credentials: 'same-origin' })
    if (!res.ok) return null
    const data = await res.json()
    if (!data?.buildId) return null
    return { buildId: String(data.buildId) }
  } catch (err) {
    if (isGenericNetworkError(err)) return null
    return null
  }
}
