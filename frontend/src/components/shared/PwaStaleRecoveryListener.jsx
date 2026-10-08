import { useEffect } from 'react'
import { markServiceWorkerUpdateWaiting } from '../../lib/appVersionUpdate.js'
import { isLikelyStaleAppError, markPwaStaleHint } from '../../lib/pwaStaleRecovery.js'

let preloadReloadScheduled = false

/** Sets a session hint when a deploy leaves an old service-worker bundle loaded. */
export function PwaStaleRecoveryListener() {
  useEffect(() => {
    function onPreloadError() {
      markPwaStaleHint()
      markServiceWorkerUpdateWaiting()
      window.dispatchEvent(new CustomEvent('insightcase:sw-waiting'))
      if (preloadReloadScheduled) return
      preloadReloadScheduled = true
      window.setTimeout(() => {
        window.location.reload()
      }, 120)
    }

    function onUnhandledRejection(event) {
      const reason = event?.reason
      if (isLikelyStaleAppError(reason)) {
        markPwaStaleHint()
      }
    }

    window.addEventListener('vite:preloadError', onPreloadError)
    window.addEventListener('unhandledrejection', onUnhandledRejection)
    return () => {
      window.removeEventListener('vite:preloadError', onPreloadError)
      window.removeEventListener('unhandledrejection', onUnhandledRejection)
    }
  }, [])

  return null
}
