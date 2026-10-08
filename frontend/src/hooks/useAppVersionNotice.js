import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  clearServiceWorkerUpdateWaiting,
  dismissVersionNoticeForSession,
  fetchRemoteVersionMeta,
  getEmbeddedBuildId,
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
  const embeddedBuildId = getEmbeddedBuildId()
  const [remoteBuildId, setRemoteBuildId] = useState(null)
  const [chunkStale, setChunkStale] = useState(() => hasPwaStaleHint())
  const [swWaiting, setSwWaiting] = useState(() => hasServiceWorkerUpdateWaiting())

  const refreshRemote = useCallback(async () => {
    const meta = await fetchRemoteVersionMeta()
    if (meta?.buildId) setRemoteBuildId(meta.buildId)
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
    }
    window.addEventListener('insightcase:sw-waiting', onSwWaiting)
    return () => window.removeEventListener('insightcase:sw-waiting', onSwWaiting)
  }, [])

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
        embeddedBuildId,
        remoteBuildId,
        chunkStale,
        swWaiting,
        standalone,
      }),
    [chunkStale, embeddedBuildId, remoteBuildId, standalone, swWaiting],
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
    embeddedBuildId,
    remoteBuildId,
    notice,
    dismissForSession,
    noteRefreshAttempt,
    showHardRecovery,
    setChunkStale,
  }
}
