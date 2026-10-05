import { useCallback, useEffect, useMemo, useState } from 'react'
import { PORTAL_PWA, isIosSafari, isStandaloneDisplay } from '../../lib/portalPwa.js'
import { refreshApp } from '../../lib/pwaUpdate.js'
import { clearPwaStaleHint, copyPortalUrlForBrowser } from '../../lib/pwaStaleRecovery.js'
import { PortalInstallSheets } from './PortalInstallSheets.jsx'
import './pwa-stale-recovery.css'

/**
 * @param {{
 *   portalId?: 'parent' | 'therapist' | 'admin'
 *   variant?: 'banner' | 'panel'
 *   forceVisible?: boolean
 *   onDismiss?: () => void
 * }} props
 */
export function PwaStaleRecoveryHelp({
  portalId = 'parent',
  variant = 'panel',
  forceVisible = false,
  onDismiss,
}) {
  const config = PORTAL_PWA[portalId] || PORTAL_PWA.parent
  const standalone = isStandaloneDisplay()
  const [expanded, setExpanded] = useState(forceVisible || variant === 'banner')
  const [sheet, setSheet] = useState(null)
  const [copyNote, setCopyNote] = useState('')

  useEffect(() => {
    if (forceVisible) setExpanded(true)
  }, [forceVisible])

  const shouldShow = forceVisible || standalone || variant === 'banner'

  const openInBrowserHint = useMemo(() => {
    if (isIosSafari()) {
      return 'In Safari, tap the address bar, open this page in a full browser tab, then sign in again.'
    }
    if (standalone) {
      return 'Open this link in Chrome or Safari (not from the home screen icon), then sign in.'
    }
    return 'Open the link in your usual browser if the shortcut misbehaves.'
  }, [standalone])

  const handleRefresh = useCallback(() => {
    clearPwaStaleHint()
    void refreshApp()
  }, [])

  const handleOpenInBrowser = useCallback(async () => {
    const { ok, url } = await copyPortalUrlForBrowser()
    setCopyNote(ok ? 'Link copied — paste it in Safari or Chrome.' : url ? `Open: ${url}` : 'Copy the address from your browser bar.')
  }, [])

  const handleDismiss = useCallback(() => {
    clearPwaStaleHint()
    onDismiss?.()
    if (variant === 'panel') setExpanded(false)
  }, [onDismiss, variant])

  if (!shouldShow && !forceVisible) return null

  if (variant === 'banner') {
    return (
      <div className="pwa-stale-banner" role="region" aria-label="App update help">
        <div className="pwa-stale-banner__copy">
          <strong>We shipped an update.</strong>
          <span> If anything looks stuck, refresh the app or open in your browser.</span>
        </div>
        <div className="pwa-stale-banner__actions">
          <button type="button" className="pwa-stale-btn pwa-stale-btn--primary" onClick={handleRefresh}>
            Get latest
          </button>
          <button type="button" className="pwa-stale-btn pwa-stale-btn--ghost" onClick={handleOpenInBrowser}>
            Open in browser
          </button>
          <button type="button" className="pwa-stale-btn pwa-stale-btn--ghost" onClick={() => setSheet('generic')}>
            Re-add shortcut
          </button>
          <button type="button" className="pwa-stale-banner__dismiss" onClick={handleDismiss} aria-label="Dismiss">
            ✕
          </button>
        </div>
        {copyNote ? <p className="pwa-stale-note">{copyNote}</p> : null}
        <PortalInstallSheets sheet={sheet} appName={config.appName} onClose={() => setSheet(null)} />
      </div>
    )
  }

  return (
    <div className={`pwa-stale-panel${expanded ? ' is-open' : ''}`}>
      {!expanded ? (
        <button
          type="button"
          className="pwa-stale-panel__toggle"
          onClick={() => setExpanded(true)}
        >
          Updated recently? Refresh your home screen app
        </button>
      ) : (
        <div className="pwa-stale-panel__body" role="region" aria-labelledby="pwa-stale-title">
          <h2 id="pwa-stale-title" className="pwa-stale-panel__title">
            Home screen app needs a quick refresh
          </h2>
          <p className="pwa-stale-panel__lead">
            After an update, the saved shortcut can keep an older copy — sign-in or pages may feel broken even with the right password.
          </p>
          <ol className="pwa-stale-panel__steps">
            <li>
              <button type="button" className="pwa-stale-btn pwa-stale-btn--primary" onClick={handleRefresh}>
                Get the latest version
              </button>
            </li>
            <li>
              <button type="button" className="pwa-stale-btn pwa-stale-btn--secondary" onClick={handleOpenInBrowser}>
                Open in browser
              </button>
              <span className="pwa-stale-panel__step-hint">{openInBrowserHint}</span>
            </li>
            <li>
              <button type="button" className="pwa-stale-btn pwa-stale-btn--secondary" onClick={() => setSheet('generic')}>
                Add shortcut again
              </button>
              <span className="pwa-stale-panel__step-hint">
                Remove the old {config.appName} icon if needed, then add it fresh from the browser menu.
              </span>
            </li>
          </ol>
          {copyNote ? <p className="pwa-stale-note">{copyNote}</p> : null}
          <button type="button" className="pwa-stale-panel__collapse" onClick={handleDismiss}>
            Close
          </button>
          <PortalInstallSheets sheet={sheet} appName={config.appName} onClose={() => setSheet(null)} />
        </div>
      )}
    </div>
  )
}
