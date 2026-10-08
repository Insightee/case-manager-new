import { useCallback, useMemo, useState } from 'react'
import { PORTAL_PWA, isStandaloneDisplay } from '../../lib/portalPwa.js'
import { refreshApp } from '../../lib/pwaUpdate.js'
import { clearPwaStaleHint, copyCanonicalPortalUrl } from '../../lib/pwaStaleRecovery.js'
import {
  formatVersionNoticeLead,
  getEmbeddedReleaseLabel,
} from '../../lib/appVersionUpdate.js'
import { getCanonicalPortalUrl } from '../../lib/canonicalAppUrl.js'
import { useAppVersionNotice } from '../../hooks/useAppVersionNotice.js'
import { AppVersionReinstallSheet } from './AppVersionReinstallSheet.jsx'
import './app-version-notice.css'

/**
 * @param {{
 *   portalId?: 'parent' | 'therapist' | 'admin'
 *   variant?: 'banner' | 'inline'
 *   testOverrides?: {
 *     embeddedReleaseLabel?: string
 *     remoteReleaseLabel?: string | null
 *     notice?: { show: boolean; buildKey: string; remoteNewer?: boolean; reinstallFallback?: boolean }
 *     standalone?: boolean
 *   }
 * }} props
 */
export function AppVersionNotice({ portalId = 'parent', variant = 'banner', testOverrides }) {
  const config = PORTAL_PWA[portalId] || PORTAL_PWA.parent
  const hook = useAppVersionNotice()
  const embeddedReleaseLabel =
    testOverrides?.embeddedReleaseLabel ?? hook.embeddedReleaseLabel ?? getEmbeddedReleaseLabel()
  const remoteReleaseLabel = testOverrides?.remoteReleaseLabel ?? hook.remoteReleaseLabel
  const notice = testOverrides?.notice ?? hook.notice
  const dismissForSession = hook.dismissForSession

  const standalone = testOverrides?.standalone ?? isStandaloneDisplay()
  const portalUrl = useMemo(() => getCanonicalPortalUrl(portalId), [portalId])
  const [sheetOpen, setSheetOpen] = useState(false)
  const [copyNote, setCopyNote] = useState('')

  const reinstallFallback = Boolean(notice.reinstallFallback)

  const handleDismiss = useCallback(() => {
    dismissForSession()
    clearPwaStaleHint()
    setSheetOpen(false)
  }, [dismissForSession])

  const handleCopy = useCallback(async () => {
    const { ok, url } = await copyCanonicalPortalUrl(portalId)
    setCopyNote(ok ? 'Link copied.' : url ? `Copy: ${url}` : 'Copy the link below.')
  }, [portalId])

  const handleReload = useCallback(() => {
    clearPwaStaleHint()
    void refreshApp()
  }, [])

  if (!notice.show) return null

  return (
    <>
      <div
        className={`app-version-notice app-version-notice--${variant}`}
        role="region"
        aria-label="App update available"
      >
        <div className="app-version-notice__copy">
          <strong className="app-version-notice__title">A new version of InsighteCase is ready.</strong>
          <p className="app-version-notice__lead">
            {remoteReleaseLabel
              ? `${formatVersionNoticeLead(embeddedReleaseLabel, remoteReleaseLabel)} InsighteCase refreshes automatically when you open it.`
              : 'A newer web build is available — reload if anything looks stuck.'}
          </p>
          <p className="app-version-notice__url-line">
            <a className="app-version-notice__url" href={portalUrl} target="_blank" rel="noopener noreferrer">
              {portalUrl}
            </a>
          </p>
        </div>
        <div className="app-version-notice__actions">
          {reinstallFallback && standalone ? (
            <button
              type="button"
              className="app-version-btn app-version-btn--primary"
              onClick={() => setSheetOpen(true)}
            >
              Install InsighteCase
            </button>
          ) : !standalone ? (
            <button type="button" className="app-version-btn app-version-btn--primary" onClick={handleReload}>
              Reload to update
            </button>
          ) : null}
          <button type="button" className="app-version-btn app-version-btn--secondary" onClick={() => void handleCopy()}>
            Copy link
          </button>
          <button type="button" className="app-version-notice__later" onClick={handleDismiss}>
            Later
          </button>
        </div>
        {copyNote ? <p className="app-version-notice__note">{copyNote}</p> : null}
      </div>
      <AppVersionReinstallSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        portalId={portalId}
        embeddedReleaseLabel={embeddedReleaseLabel}
        remoteReleaseLabel={remoteReleaseLabel}
        portalUrl={portalUrl}
        appName={config.appName}
      />
    </>
  )
}
