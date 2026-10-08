import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  clearPriorStaleBuild,
  dismissVersionNoticeForSession,
  fetchRemoteVersionMeta,
  getEmbeddedReleaseLabel,
  shouldOfferReinstallFallback,
  shouldShowVersionNotice,
} from '../lib/appVersionUpdate.js'
import { hasPwaStaleHint, isLikelyStaleAppError } from '../lib/pwaStaleRecovery.js'
import { isStandaloneDisplay } from '../lib/portalPwa.js'
import { isDeployedReleaseNewer } from '../lib/releaseLabel.js'

/**
 * Tracks deploy label for optional update notice (auto-update handled by the service worker).
 * @param {{ pollMs?: number }} [opts]
 */
export function useAppVersionNotice(opts = {}) {
  const pollMs = opts.pollMs ?? 30 * 60 * 1000
  const embeddedReleaseLabel = getEmbeddedReleaseLabel()
  const [remoteReleaseLabel, setRemoteReleaseLabel] = useState(null)
  const [chunkStale, setChunkStale] = useState(() => hasPwaStaleHint())
  const [reinstallFallback, setReinstallFallback] = useState(false)

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
    function onRejection(event) {
      const reason = event?.reason
      if (isLikelyStaleAppError(reason)) {
        setChunkStale(true)
      }
    }
    window.addEventListener('unhandledrejection', onRejection)
    return () => window.removeEventListener('unhandledrejection', onRejection)
  }, [])

  useEffect(() => {
    const remoteNewer = isDeployedReleaseNewer(embeddedReleaseLabel, remoteReleaseLabel)
    if (!remoteNewer && !chunkStale) {
      clearPriorStaleBuild()
      setReinstallFallback(false)
      return
    }
    const buildKey = remoteReleaseLabel || embeddedReleaseLabel || 'unknown'
    setReinstallFallback(shouldOfferReinstallFallback(buildKey, remoteNewer || chunkStale))
  }, [chunkStale, embeddedReleaseLabel, remoteReleaseLabel])

  const standalone = isStandaloneDisplay()

  const notice = useMemo(
    () =>
      shouldShowVersionNotice({
        embeddedReleaseLabel,
        remoteReleaseLabel,
        chunkStale,
        standalone,
      }),
    [chunkStale, embeddedReleaseLabel, remoteReleaseLabel, standalone],
  )

  const dismissForSession = useCallback(() => {
    dismissVersionNoticeForSession(notice.buildKey)
    setChunkStale(false)
  }, [notice.buildKey])

  return {
    embeddedReleaseLabel,
    remoteReleaseLabel,
    notice: { ...notice, reinstallFallback },
    dismissForSession,
    setChunkStale,
    refreshRemote,
  }
}
