/** Build / version labels for optional update notice (all portals). Auto-update is handled in main.jsx. */

import { isStandaloneDisplay } from './portalPwa.js'
import {
  getEmbeddedReleaseLabel,
  isDeployedReleaseNewer,
} from './releaseLabel.js'

export const VERSION_DISMISS_KEY = 'insightcase:version-notice-dismissed'
export const VERSION_PRIOR_STALE_KEY = 'insightcase:version-prior-stale-build'
export const VERSION_CHECK_TS_KEY = 'insightcase:version-last-check'

const MIN_CHECK_INTERVAL_MS = 5 * 60 * 1000

export function getEmbeddedBuildId() {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_BUILD_ID) {
    return String(import.meta.env.VITE_BUILD_ID)
  }
  return 'dev'
}

export { getEmbeddedReleaseLabel }

export function shouldPollRemoteVersion() {
  if (import.meta.env?.VITE_VERSION_POLL === 'true') return true
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
  return `You're on ${you}, latest is ${latest}.`
}

export function clearPriorStaleBuild() {
  if (typeof localStorage === 'undefined') return
  localStorage.removeItem(VERSION_PRIOR_STALE_KEY)
}

/**
 * After auto-update, offer reinstall guidance only if this build was already stale on a prior visit.
 * @param {string} buildKey
 * @param {boolean} remoteNewer
 */
export function shouldOfferReinstallFallback(buildKey, remoteNewer) {
  if (!remoteNewer) {
    clearPriorStaleBuild()
    return false
  }
  if (typeof localStorage === 'undefined') return false
  const key = buildKey || 'unknown'
  const prior = localStorage.getItem(VERSION_PRIOR_STALE_KEY)
  if (prior === key) return true
  localStorage.setItem(VERSION_PRIOR_STALE_KEY, key)
  return false
}

/**
 * @param {'ios' | 'android' | 'desktop'} platform
 * @param {{ portalUrl: string, appName: string }} ctx
 */
export function getReinstallSteps(platform, { portalUrl, appName }) {
  const link = portalUrl || 'your InsighteCase link'
  if (platform === 'ios') {
    return [
      { id: 'copy', kind: 'action', action: 'copy', label: 'Copy link' },
      {
        id: 'remove',
        kind: 'text',
        text: `Press and hold the old ${appName} icon on your home screen, then choose Remove App → Delete from Home Screen.`,
      },
      {
        id: 'open-safari',
        kind: 'action',
        action: 'open_safari',
        label: 'Open in Safari',
        hint: 'Paste the link in Safari if it does not open automatically.',
      },
      {
        id: 'add',
        kind: 'text',
        text: 'Tap Share → Add to Home Screen → Add.',
      },
    ]
  }
  if (platform === 'android') {
    return [
      { id: 'copy', kind: 'action', action: 'copy', label: 'Copy link' },
      {
        id: 'remove',
        kind: 'text',
        text: `Remove the old ${appName} home screen shortcut (press and hold the icon → Uninstall or Remove).`,
      },
      {
        id: 'open-chrome',
        kind: 'action',
        action: 'open_browser',
        label: 'Open in Chrome',
        hint: `Paste ${link} in Chrome if needed.`,
      },
      {
        id: 'install',
        kind: 'text',
        text: 'Tap ⋮ → Install app or Add to Home screen to add the shortcut again.',
      },
    ]
  }
  return [
    { id: 'copy', kind: 'action', action: 'copy', label: 'Copy link' },
    {
      id: 'open',
      kind: 'action',
      action: 'open_browser',
      label: 'Open in Chrome or Edge tab',
      hint: 'Use a normal browser tab — not the installed shortcut window.',
    },
    {
      id: 'remove',
      kind: 'text',
      text: `Remove the old ${appName} shortcut. Chrome: in the app window, open the ⋮ menu → Uninstall ${appName}, or visit chrome://apps, right‑click the icon → Remove. Edge: … → Apps → Manage apps → remove the old shortcut.`,
    },
    {
      id: 'install',
      kind: 'text',
      text: 'Re-add the shortcut: use the install icon in the address bar, or Chrome ⋮ → Save and share → Install page as app (Edge: Apps → Install this site as an app).',
    },
  ]
}

/**
 * @param {string | { userAgent?: string, platform?: string, maxTouchPoints?: number }} [input]
 * @returns {'ios' | 'android' | 'desktop'}
 */
export function detectReinstallPlatform(input) {
  const env =
    typeof input === 'string'
      ? { userAgent: input }
      : input != null && typeof input === 'object'
        ? input
        : {}

  const ua = env.userAgent ?? (typeof navigator !== 'undefined' ? navigator.userAgent : '')
  const platform = env.platform ?? (typeof navigator !== 'undefined' ? navigator.platform : '')
  const maxTouchPoints =
    env.maxTouchPoints ?? (typeof navigator !== 'undefined' ? navigator.maxTouchPoints : 0)

  if (/iPad|iPhone|iPod/i.test(ua)) return 'ios'
  if (platform === 'MacIntel' && maxTouchPoints > 1) return 'ios'
  if (/Android/i.test(ua)) return 'android'
  return 'desktop'
}

/**
 * @param {string} httpsUrl
 * @returns {string}
 */
export function buildIosSafariOpenUrl(httpsUrl) {
  const raw = String(httpsUrl || '').trim()
  if (!raw) return ''
  if (raw.startsWith('x-safari-https://')) return raw
  const stripped = raw.replace(/^https:\/\//i, '')
  return `x-safari-https://${stripped}`
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
 * @param {{
 *   embeddedReleaseLabel: string
 *   remoteReleaseLabel?: string | null
 *   chunkStale?: boolean
 *   standalone?: boolean
 * }} input
 */
export function shouldShowVersionNotice(input) {
  const {
    embeddedReleaseLabel,
    remoteReleaseLabel = null,
    chunkStale = false,
    standalone = isStandaloneDisplay(),
  } = input

  const remoteNewer = isDeployedReleaseNewer(embeddedReleaseLabel, remoteReleaseLabel)
  const buildKey = remoteReleaseLabel || embeddedReleaseLabel || 'unknown'

  if (!remoteNewer && !chunkStale) {
    return { show: false, buildKey, remoteNewer: false, reinstallFallback: false }
  }

  if (isVersionNoticeDismissed(buildKey) && remoteNewer && !chunkStale) {
    return { show: false, buildKey, remoteNewer: false, reinstallFallback: false }
  }

  return {
    show: true,
    buildKey,
    remoteNewer,
    reinstallFallback: false,
  }
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
