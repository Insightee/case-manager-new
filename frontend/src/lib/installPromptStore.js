/**
 * Captures the browser's beforeinstallprompt / appinstalled events as early as possible
 * (called from main.jsx before React renders) so the ?reinstall=1 landing never misses them.
 * Chrome and Edge only; Safari never fires these events.
 */

/** @type {any} */
let deferredPrompt = null
let installedThisVisit = false
/** @type {Set<() => void>} */
const listeners = new Set()

function emit() {
  listeners.forEach((fn) => {
    try {
      fn()
    } catch {
      // listener errors must not break capture
    }
  })
}

export function initInstallPromptCapture(target = typeof window !== 'undefined' ? window : null) {
  if (!target || target.__insighteInstallCaptureReady) return
  target.__insighteInstallCaptureReady = true
  target.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault?.()
    deferredPrompt = event
    emit()
  })
  target.addEventListener('appinstalled', () => {
    deferredPrompt = null
    installedThisVisit = true
    emit()
  })
}

export function getDeferredInstallPrompt() {
  return deferredPrompt
}

export function wasInstalledThisVisit() {
  return installedThisVisit
}

/**
 * Show the browser's install dialog once. A prompt event can only be used once.
 * @returns {Promise<{ outcome: 'accepted' | 'dismissed' | 'unavailable' }>}
 */
export async function promptDeferredInstall() {
  const event = deferredPrompt
  if (!event || typeof event.prompt !== 'function') return { outcome: 'unavailable' }
  deferredPrompt = null
  emit()
  try {
    await event.prompt()
    const choice = await event.userChoice
    const outcome = choice?.outcome === 'accepted' ? 'accepted' : 'dismissed'
    if (outcome === 'accepted') installedThisVisit = true
    emit()
    return { outcome }
  } catch {
    return { outcome: 'unavailable' }
  }
}

/** @param {() => void} fn */
export function subscribeInstallPrompt(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

/** Test-only reset. */
export function __resetInstallPromptStoreForTests() {
  deferredPrompt = null
  installedThisVisit = false
  listeners.clear()
}
