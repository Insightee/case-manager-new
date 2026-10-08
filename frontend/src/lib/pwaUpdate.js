/** Shared PWA update hook — register once from main.jsx. */

let applyUpdate = null

export function setPwaUpdateHandler(fn) {
  applyUpdate = typeof fn === 'function' ? fn : null
}

/**
 * Apply a waiting service worker when present, otherwise reload the page.
 * @param {{ reload?: () => void, update?: ((reloadPage?: boolean) => unknown) | null }} [opts]
 */
export async function refreshApp(opts = {}) {
  const reload = opts.reload || (() => window.location.reload())
  const update = opts.update !== undefined ? opts.update : applyUpdate
  if (typeof update === 'function') {
    try {
      await update(true)
      return
    } catch {
      // Fall through to a hard reload so field therapists are never stuck.
    }
  }
  reload()
}
