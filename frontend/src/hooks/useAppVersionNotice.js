import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  clearPriorStaleBuild,
  dismissVersionNoticeForSession,
  fetchRemoteVersionMeta,
  getEmbeddedReleaseLabel,
  readCachedRemoteVersionMeta,
  startVersionCheckScheduler,
  VERSION_META_EVENT,
  VERSION_REMOTE_META_KEY,
  shouldOfferReinstallFallback,
  shouldShowVersionNotice,
} from '../lib/appVersionUpdate.js'
import { hasPwaStaleHint, isLikelyStaleAppError } from '../lib/pwaStaleRecovery.js'
import { isStandaloneDisplay } from '../lib/portalPwa.js'
import { isDeployedReleaseNewer } from '../lib/releaseLabel.js'

/**
 * Tracks deploy label for optional update notice (auto-update handled by the service worker).
 * /version.json is fetched at most once per VERSION_CHECK_INTERVAL_MS (12h) per device; every
 * hook instance, tab and portal reads the shared cached result.
 */
export function useAppVersionNotice() {
  const embeddedReleaseLabel = getEmbeddedReleaseLabel()
  const [remoteReleaseLabel, setRemoteReleaseLabel] = useState(
    () => readCachedRemoteVersionMeta()?.releaseLabel ?? null,
  )
  const [chunkStale, setChunkStale] = useState(() => hasPwaStaleHint())
  const [reinstallFallback, setReinstallFallback] = useState(false)

  const refreshRemote = useCallback(async () => {
    const meta = await fetchRemoteVersionMeta()
    if (meta?.releaseLabel) setRemoteReleaseLabel(meta.releaseLabel)
  }, [])

  useEffect(() => {
    // Adopt results from this tab's scheduler or another tab; these listeners never hit the network.
    const adoptCached = () => {
      const meta = readCachedRemoteVersionMeta()
      if (meta?.releaseLabel) setRemoteReleaseLabel(meta.releaseLabel)
    }
    const onStorage = (event) => {
      if (event.key === VERSION_REMOTE_META_KEY) adoptCached()
    }
    window.addEventListener(VERSION_META_EVENT, adoptCached)
    window.addEventListener('storage', onStorage)
    startVersionCheckScheduler()
    return () => {
      window.removeEventListener(VERSION_META_EVENT, adoptCached)
      window.removeEventListener('storage', onStorage)
    }
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
