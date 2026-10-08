import { useCallback, useEffect, useState } from 'react'
import { PORTAL_PWA, isStandaloneDisplay } from '../../lib/portalPwa.js'
import { refreshApp } from '../../lib/pwaUpdate.js'
import {
  clearPwaStaleHint,
  copyPortalUrlForBrowser,
  portalUrlForBrowser,
} from '../../lib/pwaStaleRecovery.js'
import {
  detectReinstallPlatform,
  formatVersionNoticeLead,
  getReinstallSteps,
  getEmbeddedReleaseLabel,
} from '../../lib/appVersionUpdate.js'
import { useAppVersionNotice } from '../../hooks/useAppVersionNotice.js'
import { PwaStaleRecoveryHelp } from './PwaStaleRecoveryHelp.jsx'
import './app-version-notice.css'

/**
 * @param {{
 *   portalId?: 'parent' | 'therapist' | 'admin'
 *   variant?: 'banner' | 'inline'
 * }} props
 */
export function AppVersionNotice({ portalId = 'parent', variant = 'banner' }) {
  const config = PORTAL_PWA[portalId] || PORTAL_PWA.parent
  const {
    notice,
    dismissForSession,
    noteRefreshAttempt,
    showHardRecovery,
    embeddedReleaseLabel,
    remoteReleaseLabel,
  } = useAppVersionNotice()
  const embedded = embeddedReleaseLabel || getEmbeddedReleaseLabel()
  const [copyNote, setCopyNote] = useState('')
  const portalUrl = portalUrlForBrowser() || window.location.origin

  const handleRefresh = useCallback(async () => {
    clearPwaStaleHint()
    noteRefreshAttempt()
    await refreshApp()
  }, [noteRefreshAttempt])

  const handleDismiss = useCallback(() => {
    dismissForSession()
    clearPwaStaleHint()
  }, [dismissForSession])

  const handleCopy = useCallback(async () => {
    const { ok } = await copyPortalUrlForBrowser()
    setCopyNote(ok ? 'Link copied.' : 'Copy the address from your browser bar.')
  }, [])

  useEffect(() => {
    if (notice.show && notice.mode === 'hard') {
      showHardRecovery()
    }
  }, [notice.mode, notice.show, showHardRecovery])

  if (!notice.show) return null

  if (notice.mode === 'hard') {
    const platform = detectReinstallPlatform()
    const steps = getReinstallSteps(platform, {
      portalUrl,
      appName: config.appName,
    })
    return (
      <div className="app-version-sheet" role="dialog" aria-modal="true" aria-labelledby="app-version-title">
        <div className="app-version-sheet__panel">
          <h2 id="app-version-title" className="app-version-sheet__title">
            A new version of Insighte is available.
          </h2>
          <p className="app-version-sheet__lead">
            {formatVersionNoticeLead(embedded, remoteReleaseLabel)} Re-add the shortcut using these steps:
          </p>
          <ol className="app-version-sheet__steps">
            {steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <div className="app-version-sheet__actions">
            <button type="button" className="pwa-stale-btn pwa-stale-btn--primary" onClick={() => void handleRefresh()}>
              Refresh now
            </button>
            <button type="button" className="pwa-stale-btn pwa-stale-btn--secondary" onClick={() => void handleCopy()}>
              Copy link
            </button>
            <a href={portalUrl} target="_blank" rel="noopener noreferrer">
              Open in browser
            </a>
            <button type="button" className="pwa-stale-btn pwa-stale-btn--ghost" onClick={handleDismiss}>
              Not now
            </button>
          </div>
          {copyNote ? <p className="pwa-stale-note">{copyNote}</p> : null}
        </div>
      </div>
    )
  }

  return (
    <div className={`app-version-notice--${variant}`}>
      <PwaStaleRecoveryHelp
        portalId={portalId}
        variant="banner"
        forceVisible
        onDismiss={handleDismiss}
        onRefresh={handleRefresh}
        title="A new version of Insighte is available."
        lead={
          remoteReleaseLabel
            ? formatVersionNoticeLead(embedded, remoteReleaseLabel)
            : isStandaloneDisplay()
              ? 'Tap Refresh now to load the latest build.'
              : 'Refresh to load the latest version.'
        }
      />
    </div>
  )
}
