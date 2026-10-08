import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  clearServiceWorkerUpdateWaiting,
  dismissVersionNoticeForSession,
  fetchRemoteVersionMeta,
  getEmbeddedReleaseLabel,
  hasServiceWorkerUpdateWaiting,
  markHardRecoveryShown,
  recordRefreshAttempt,
  shouldShowVersionNotice,
} from '../lib/appVersionUpdate.js'
import { hasPwaStaleHint, isLikelyStaleAppError } from '../lib/pwaStaleRecovery.js'
import { isStandaloneDisplay } from '../lib/portalPwa.js'

/**
 * Tracks deploy / chunk / service-worker stale state for PWA update prompts.
 * @param {{ pollMs?: number }} [opts]
 */
export function useAppVersionNotice(opts = {}) {
  const pollMs = opts.pollMs ?? 30 * 60 * 1000
  const embeddedReleaseLabel = getEmbeddedReleaseLabel()
  const [remoteReleaseLabel, setRemoteReleaseLabel] = useState(null)
  const [chunkStale, setChunkStale] = useState(() => hasPwaStaleHint())
  const [swWaiting, setSwWaiting] = useState(() => hasServiceWorkerUpdateWaiting())

  const refreshRemote = useCallback(async () => {
    const meta = await fetchRemoteVersionMeta()
    if (meta?.releaseLabel) setRemoteReleaseLabel(meta.releaseLabel)
  }, [])

  useEffect(() => {
    void refreshRemote()
    const onFocus = () => void refreshRemote()
    window.addEventListener('focus', onFocus)
    const timer = window.setInterval(() => void refreshRemote(), pollMs)
    return () => {
      window.removeEventListener('focus', onFocus)
      window.clearInterval(timer)
    }
  }, [pollMs, refreshRemote])

  useEffect(() => {
    function onSwWaiting() {
      setSwWaiting(true)
      void refreshRemote()
    }
    window.addEventListener('insightcase:sw-waiting', onSwWaiting)
    return () => window.removeEventListener('insightcase:sw-waiting', onSwWaiting)
  }, [refreshRemote])

  useEffect(() => {
    function onRejection(event) {
      const reason = event?.reason
      if (isLikelyStaleAppError(reason)) {
        setChunkStale(true)
      }
    }
    window.addEventListener('unhandledrejection', onRejection)
    return () => window.removeEventListener('unhandledrejection', onRejection)
  }, [])

  const standalone = isStandaloneDisplay()

  const notice = useMemo(
    () =>
      shouldShowVersionNotice({
        embeddedReleaseLabel,
        remoteReleaseLabel,
        chunkStale,
        swWaiting,
        standalone,
      }),
    [chunkStale, embeddedReleaseLabel, remoteReleaseLabel, standalone, swWaiting],
  )

  const dismissForSession = useCallback(() => {
    dismissVersionNoticeForSession(notice.buildKey)
    setChunkStale(false)
    setSwWaiting(false)
    clearServiceWorkerUpdateWaiting()
  }, [notice.buildKey])

  const noteRefreshAttempt = useCallback(() => {
    recordRefreshAttempt()
    clearServiceWorkerUpdateWaiting()
    setSwWaiting(false)
  }, [])

  const showHardRecovery = useCallback(() => {
    markHardRecoveryShown()
  }, [])

  return {
    embeddedReleaseLabel,
    remoteReleaseLabel,
    notice,
    dismissForSession,
    noteRefreshAttempt,
    showHardRecovery,
    setChunkStale,
    refreshRemote,
  }
}
