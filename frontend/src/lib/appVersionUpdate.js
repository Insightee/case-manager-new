/** Build / version labels for optional update notice (all portals). Auto-update is handled in main.jsx. */

import { isStandaloneDisplay } from './portalPwa.js'
import {
  getEmbeddedReleaseLabel,
  isDeployedReleaseNewer,
} from './releaseLabel.js'

export const VERSION_DISMISS_KEY = 'insightcase:version-notice-dismissed'
export const VERSION_PRIOR_STALE_KEY = 'insightcase:version-prior-stale-build'
export const VERSION_CHECK_TS_KEY = 'insightcase:version-last-check'
export const VERSION_REMOTE_META_KEY = 'insightcase:version-remote-meta'
/** Fired in this tab after a version.json result is stored (other tabs get the 'storage' event). */
export const VERSION_META_EVENT = 'insightcase:version-meta'

/**
 * The ONE knob for how often a device asks the server for /version.json: at most once per 12 hours,
 * shared by every tab, reload and portal (parent, therapist, admin) via localStorage.
 * Service-worker updates still happen on normal page loads (browser's own sw.js check).
 */
export const VERSION_CHECK_INTERVAL_MS = 12 * 60 * 60 * 1000

/** Fallback when localStorage is unavailable (private mode / blocked): once per page lifetime window. */
let memoryLastCheck = 0
/** @type {Promise<{ buildId: string, releaseLabel: string } | null> | null} */
let inflightVersionFetch = null

function safeLocalStorage() {
  try {
    if (typeof localStorage === 'undefined') return null
    return localStorage
  } catch {
    return null
  }
}

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
 * Re-add shortcut steps for the browsers we support: Chrome, Safari and Edge.
 * Other browsers fall back to the closest of these (Chromium-style on Android
 * and desktop, the shared iOS home-screen flow on iPhone).
 * @param {'ios' | 'ios-chrome' | 'ios-edge' | 'android' | 'android-edge' | 'mac-safari' | 'desktop' | 'desktop-edge'} platform
 * @param {{ portalUrl: string, appName: string }} ctx
 */
export function getReinstallSteps(platform, { portalUrl, appName }) {
  const link = portalUrl || 'your InsighteCase link'
  const copyStep = { id: 'copy', kind: 'action', action: 'copy', label: 'Copy link' }
  const androidRemove = {
    id: 'remove',
    kind: 'text',
    text: `Remove the old ${appName} home screen shortcut (press and hold the icon → Uninstall or Remove).`,
  }

  if (platform === 'ios' || platform === 'ios-chrome' || platform === 'ios-edge') {
    const browser = platform === 'ios-chrome' ? 'Chrome' : platform === 'ios-edge' ? 'Edge' : 'Safari'
    return [
      copyStep,
      {
        id: 'remove',
        kind: 'text',
        text: `Press and hold the old ${appName} icon on your home screen, then choose Remove App → Delete from Home Screen.`,
      },
      {
        id: 'open-browser',
        kind: 'action',
        action: platform === 'ios' ? 'open_safari' : 'open_browser',
        label: `Open in ${browser}`,
        hint: `Paste the link in ${browser} if it does not open automatically. Safari, Chrome and Edge on iPhone all use the same steps.`,
      },
      {
        id: 'add',
        kind: 'text',
        text:
          browser === 'Safari'
            ? 'Tap Share (the square with an arrow) → Add to Home Screen → Add.'
            : `Tap the Share icon in the address bar, or ⋯ → Share → Add to Home Screen → Add.`,
      },
    ]
  }

  if (platform === 'android' || platform === 'android-edge') {
    const browser = platform === 'android-edge' ? 'Edge' : 'Chrome'
    return [
      copyStep,
      androidRemove,
      {
        id: 'open-browser',
        kind: 'action',
        action: 'open_browser',
        label: `Open in ${browser}`,
        hint: `Paste ${link} in ${browser} if needed.`,
      },
      {
        id: 'install',
        kind: 'text',
        text:
          browser === 'Edge'
            ? 'Tap … → Add to phone → Install app (or Add to Home screen) → Add.'
            : 'Tap ⋮ → Install app or Add to Home screen → Add.',
      },
    ]
  }

  if (platform === 'mac-safari') {
    return [
      copyStep,
      {
        id: 'remove',
        kind: 'text',
        text: `Quit the old ${appName} app, then in Finder open Applications (or your home folder → Applications) and move ${appName} to the Trash (Bin).`,
      },
      {
        id: 'open',
        kind: 'action',
        action: 'open_browser',
        label: 'Open in Safari',
        hint: 'Paste the link in a normal Safari window if it does not open automatically.',
      },
      {
        id: 'install',
        kind: 'text',
        text: 'In Safari choose File → Add to Dock (or Share → Add to Dock) → Add.',
      },
    ]
  }

  if (platform === 'desktop-edge') {
    return [
      copyStep,
      {
        id: 'open',
        kind: 'action',
        action: 'open_browser',
        label: 'Open in Edge',
        hint: 'Use a normal Edge tab, not the installed app window.',
      },
      {
        id: 'remove',
        kind: 'text',
        text: `Remove the old ${appName} shortcut: in the app window open … → App settings → Uninstall, or go to edge://apps, right‑click the icon → Uninstall.`,
      },
      {
        id: 'install',
        kind: 'text',
        text: 'Re-add it: use the install icon in the address bar, or … → Apps → Install this site as an app → Install.',
      },
    ]
  }

  return [
    copyStep,
    {
      id: 'open',
      kind: 'action',
      action: 'open_browser',
      label: 'Open in Chrome',
      hint: 'Use a normal Chrome tab, not the installed shortcut window.',
    },
    {
      id: 'remove',
      kind: 'text',
      text: `Remove the old ${appName} shortcut: in the app window open ⋮ → Uninstall ${appName}, or go to chrome://apps, right‑click the icon → Remove.`,
    },
    {
      id: 'install',
      kind: 'text',
      text: 'Re-add the shortcut: use the install icon in the address bar, or ⋮ → Cast, save and share → Install page as app.',
    },
  ]
}

/**
 * @param {string | { userAgent?: string, platform?: string, maxTouchPoints?: number }} [input]
 * @returns {'ios' | 'ios-chrome' | 'ios-edge' | 'android' | 'android-edge' | 'mac-safari' | 'desktop' | 'desktop-edge'}
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

  // Every iPhone / iPad browser is WebKit. Name the three we support; anything else gets Safari's steps.
  if (/iPad|iPhone|iPod/i.test(ua) || (platform === 'MacIntel' && maxTouchPoints > 1)) {
    if (/CriOS/i.test(ua)) return 'ios-chrome'
    if (/EdgiOS/i.test(ua)) return 'ios-edge'
    return 'ios'
  }
  if (/Android/i.test(ua)) {
    if (/EdgA\//i.test(ua)) return 'android-edge'
    return 'android'
  }
  if (/Edg\//i.test(ua)) return 'desktop-edge'
  if (/Macintosh|Mac OS X/i.test(ua) && /Safari\//i.test(ua) && !/Chrome|Chromium|CriOS|Edg|OPR|Firefox/i.test(ua)) {
    return 'mac-safari'
  }
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

/**
 * @param {{ now?: number, storage?: Storage | null }} [opts]
 * @returns {number} epoch ms of the last version.json check on this device (0 if never)
 */
export function getLastVersionCheck(opts = {}) {
  const storage = opts.storage !== undefined ? opts.storage : safeLocalStorage()
  if (!storage) return memoryLastCheck
  try {
    const last = Number(storage.getItem(VERSION_CHECK_TS_KEY))
    return Number.isFinite(last) && last > 0 ? last : 0
  } catch {
    return memoryLastCheck
  }
}

/**
 * True when no check has happened on this device in the last VERSION_CHECK_INTERVAL_MS.
 * A timestamp in the future (clock moved back) counts as due so a device can't get stuck.
 * @param {{ now?: number, storage?: Storage | null }} [opts]
 */
export function canCheckVersionNow(opts = {}) {
  const now = opts.now ?? Date.now()
  const last = getLastVersionCheck(opts)
  if (!last) return true
  const elapsed = now - last
  if (elapsed < 0) return true
  return elapsed >= VERSION_CHECK_INTERVAL_MS
}

/** @param {{ now?: number, storage?: Storage | null }} [opts] */
export function msUntilNextVersionCheck(opts = {}) {
  const now = opts.now ?? Date.now()
  const last = getLastVersionCheck(opts)
  if (!last || now < last) return 0
  return Math.max(0, last + VERSION_CHECK_INTERVAL_MS - now)
}

/** @param {{ now?: number, storage?: Storage | null }} [opts] */
export function markVersionChecked(opts = {}) {
  const now = opts.now ?? Date.now()
  memoryLastCheck = now
  const storage = opts.storage !== undefined ? opts.storage : safeLocalStorage()
  try {
    storage?.setItem(VERSION_CHECK_TS_KEY, String(now))
  } catch {
    // memory fallback already set
  }
}

const RELEASE_LABEL_RE = /^[A-Za-z0-9._-]{1,40}$/

/**
 * Last version.json result on this device (shared across tabs/portals).
 * @param {{ storage?: Storage | null }} [opts]
 * @returns {{ buildId: string, releaseLabel: string } | null}
 */
export function readCachedRemoteVersionMeta(opts = {}) {
  const storage = opts.storage !== undefined ? opts.storage : safeLocalStorage()
  if (!storage) return null
  try {
    const data = JSON.parse(storage.getItem(VERSION_REMOTE_META_KEY) || 'null')
    if (!data || typeof data.releaseLabel !== 'string' || !RELEASE_LABEL_RE.test(data.releaseLabel)) return null
    return {
      buildId: typeof data.buildId === 'string' ? data.buildId.slice(0, 64) : '',
      releaseLabel: data.releaseLabel,
    }
  } catch {
    return null
  }
}

function storeRemoteVersionMeta(meta, storage) {
  try {
    storage?.setItem(VERSION_REMOTE_META_KEY, JSON.stringify(meta))
  } catch {
    // ignore
  }
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function' && typeof Event === 'function') {
    window.dispatchEvent(new Event(VERSION_META_EVENT))
  }
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
 * Version metadata for the notice: the cached result, refreshed from /version.json at most once
 * per VERSION_CHECK_INTERVAL_MS per device. Concurrent callers in a tab share one request.
 * @param {{
 *   now?: number
 *   storage?: Storage | null
 *   fetchImpl?: typeof fetch
 *   enabled?: boolean
 * }} [opts]
 * @returns {Promise<{ buildId: string, releaseLabel: string } | null>}
 */
export async function fetchRemoteVersionMeta(opts = {}) {
  const enabled = opts.enabled ?? shouldPollRemoteVersion()
  if (!enabled) return null
  const storage = opts.storage !== undefined ? opts.storage : safeLocalStorage()
  if (inflightVersionFetch) return inflightVersionFetch
  if (!canCheckVersionNow({ now: opts.now, storage })) return readCachedRemoteVersionMeta({ storage })

  // Mark first so other tabs / portals opened right now skip their own request.
  markVersionChecked({ now: opts.now, storage })
  const fetchImpl = opts.fetchImpl || (typeof fetch === 'function' ? fetch : null)
  if (!fetchImpl) return readCachedRemoteVersionMeta({ storage })

  inflightVersionFetch = (async () => {
    try {
      const url = `/version.json?t=${opts.now ?? Date.now()}`
      const res = await fetchImpl(url, { cache: 'no-store', credentials: 'same-origin' })
      if (!res.ok) return readCachedRemoteVersionMeta({ storage })
      const data = await res.json()
      const releaseLabel = data?.releaseLabel ? String(data.releaseLabel) : ''
      if (!RELEASE_LABEL_RE.test(releaseLabel)) return readCachedRemoteVersionMeta({ storage })
      const meta = {
        buildId: data.buildId ? String(data.buildId).slice(0, 64) : '',
        releaseLabel,
      }
      storeRemoteVersionMeta(meta, storage)
      return meta
    } catch (err) {
      if (isGenericNetworkError(err)) return readCachedRemoteVersionMeta({ storage })
      return readCachedRemoteVersionMeta({ storage })
    } finally {
      inflightVersionFetch = null
    }
  })()
  return inflightVersionFetch
}

/** Test-only reset of module state. */
export function __resetVersionCheckStateForTests() {
  memoryLastCheck = 0
  inflightVersionFetch = null
}

let schedulerTimer = null

/**
 * One scheduler per tab (idempotent): checks on start only if the last device-wide check is
 * older than VERSION_CHECK_INTERVAL_MS, then wakes when the next 12h window opens. No focus,
 * visibility or route-change checks. Other tabs' results arrive through the 'storage' event.
 * @param {{ setTimer?: typeof setTimeout }} [opts]
 */
export function startVersionCheckScheduler(opts = {}) {
  if (schedulerTimer !== null) return
  if (!shouldPollRemoteVersion() && !opts.force) return
  const setTimer = opts.setTimer || ((fn, ms) => setTimeout(fn, ms))
  const tick = () => {
    void fetchRemoteVersionMeta({ enabled: true }).finally(() => {
      // Floor of 1 minute so a broken clock or storage can never spin this into a loop.
      const wait = Math.max(60_000, msUntilNextVersionCheck() || VERSION_CHECK_INTERVAL_MS)
      schedulerTimer = setTimer(tick, wait)
    })
  }
  schedulerTimer = 'starting'
  tick()
}

/** Test-only. */
export function __resetVersionSchedulerForTests() {
  if (schedulerTimer && schedulerTimer !== 'starting') clearTimeout(schedulerTimer)
  schedulerTimer = null
}
