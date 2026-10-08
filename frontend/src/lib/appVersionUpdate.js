/** Build / service-worker version detection for PWA update prompts (all portals). */

import { isStandaloneDisplay } from './portalPwa.js'
import {
  getEmbeddedReleaseLabel,
  isDeployedReleaseNewer,
} from './releaseLabel.js'

export const VERSION_DISMISS_KEY = 'insightcase:version-notice-dismissed'
export const VERSION_REFRESH_ATTEMPTS_KEY = 'insightcase:version-refresh-attempts'
export const SW_UPDATE_WAITING_KEY = 'insightcase:sw-update-waiting'
export const VERSION_CHECK_TS_KEY = 'insightcase:version-last-check'
export const HARD_RECOVERY_SHOWN_KEY = 'insightcase:version-hard-shown'

const MIN_CHECK_INTERVAL_MS = 5 * 60 * 1000
const MAX_SOFT_REFRESH_ATTEMPTS = 2

export function getEmbeddedBuildId() {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_BUILD_ID) {
    return String(import.meta.env.VITE_BUILD_ID)
  }
  return 'dev'
}

export { getEmbeddedReleaseLabel }

export function shouldPollRemoteVersion() {
  return Boolean(import.meta.env?.PROD)
}

/** @deprecated use isDeployedReleaseNewer */
export function isRemoteBuildNewer(embedded, remote) {
  return isDeployedReleaseNewer(embedded, remote)
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
 * @param {string} embedded
 * @param {string | null | undefined} remote
 */
export function formatVersionNoticeLead(embedded, remote) {
  const you = embedded || 'unknown'
  const latest = remote || 'unknown'
  return `You're on ${you}, latest is ${latest}. Tap Refresh now to load the latest build.`
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

export function dismissVersionNoticeForSession(releaseKey) {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(VERSION_DISMISS_KEY, releaseKey || 'unknown')
}

export function isVersionNoticeDismissed(releaseKey) {
  if (typeof sessionStorage === 'undefined') return false
  const dismissed = sessionStorage.getItem(VERSION_DISMISS_KEY)
  return dismissed && releaseKey && dismissed === releaseKey
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
 * Soft notice only when deployed release label is newer than the embedded client label.
 * @param {{
 *   embeddedReleaseLabel: string
 *   remoteReleaseLabel?: string | null
 *   chunkStale?: boolean
 *   swWaiting?: boolean
 *   standalone?: boolean
 * }} input
 */
export function shouldShowVersionNotice(input) {
  const {
    embeddedReleaseLabel,
    remoteReleaseLabel = null,
    chunkStale = false,
    swWaiting = false,
    standalone = isStandaloneDisplay(),
  } = input

  const remoteNewer = isDeployedReleaseNewer(embeddedReleaseLabel, remoteReleaseLabel)
  const buildKey = remoteReleaseLabel || embeddedReleaseLabel || 'unknown'

  if (!remoteNewer) return { show: false, mode: 'none', buildKey, remoteNewer: false }

  if (isVersionNoticeDismissed(buildKey) && !chunkStale) {
    return { show: false, mode: 'none', buildKey, remoteNewer: false }
  }

  const refreshAttempts = getRefreshAttemptCount()
  const hardEligible =
    standalone &&
    remoteNewer &&
    refreshAttempts >= MAX_SOFT_REFRESH_ATTEMPTS &&
    !wasHardRecoveryShown()

  if (hardEligible) {
    return { show: true, mode: 'hard', buildKey, remoteNewer: true }
  }

  return { show: true, mode: 'soft', buildKey, remoteNewer: true }
}

/**
 * Fetch /version.json (cache-busted lightly).
 * @returns {Promise<{ buildId: string, releaseLabel: string } | null>}
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
    if (!data?.releaseLabel) return null
    return {
      buildId: data.buildId ? String(data.buildId) : '',
      releaseLabel: String(data.releaseLabel),
    }
  } catch (err) {
    if (isGenericNetworkError(err)) return null
    return null
  }
}
