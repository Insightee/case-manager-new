import { useEffect } from 'react'
import { isLikelyStaleAppError, markPwaStaleHint } from '../../lib/pwaStaleRecovery.js'

/** Sets a session hint when a deploy leaves an old service-worker bundle loaded. */
export function PwaStaleRecoveryListener() {
  useEffect(() => {
    function onPreloadError(event) {
      markPwaStaleHint()
      event?.preventDefault?.()
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
