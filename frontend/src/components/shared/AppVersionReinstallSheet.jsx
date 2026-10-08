import { useCallback, useState } from 'react'
import { createPortal } from 'react-dom'
import { formatVersionNoticeLead } from '../../lib/appVersionUpdate.js'
import { getCanonicalPortalUrl } from '../../lib/canonicalAppUrl.js'
import {
  appendReinstallParam,
  detectReinstallPlatform,
  getRemoveAppOneLiner,
  launchReinstallInBrowser,
} from '../../lib/pwaReinstall.js'
import { copyCanonicalPortalUrl } from '../../lib/pwaStaleRecovery.js'
import './app-version-notice.css'

/**
 * @param {{
 *   open: boolean
 *   onClose: () => void
 *   portalId: 'parent' | 'therapist' | 'admin'
 *   embeddedReleaseLabel: string
 *   remoteReleaseLabel: string | null
 *   portalUrl: string
 *   appName: string
 * }} props
 */
export function AppVersionReinstallSheet({
  open,
  onClose,
  portalId,
  embeddedReleaseLabel,
  remoteReleaseLabel,
  portalUrl,
  appName,
}) {
  const platform = detectReinstallPlatform()
  const isIos = platform.startsWith('ios')
  const removeLine = getRemoveAppOneLiner(platform, appName)
  const [copyNote, setCopyNote] = useState('')

  const reinstallUrl = appendReinstallParam(portalUrl || getCanonicalPortalUrl(portalId))

  const handleInstall = useCallback(() => {
    launchReinstallInBrowser(platform, portalUrl || getCanonicalPortalUrl(portalId))
  }, [platform, portalId, portalUrl])

  const handleCopy = useCallback(async () => {
    const { ok, url } = await copyCanonicalPortalUrl(portalId)
    const withFlag = appendReinstallParam(url || reinstallUrl)
    if (ok && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(withFlag)
        setCopyNote('Link copied.')
        return
      } catch {
        // fall through
      }
    }
    setCopyNote(ok ? 'Link copied.' : `Copy: ${withFlag}`)
  }, [portalId, reinstallUrl])

  if (!open) return null

  return createPortal(
    <div className="app-version-sheet" role="presentation" onClick={onClose}>
      <div
        className="app-version-sheet__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="app-version-reinstall-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="app-version-reinstall-title" className="app-version-sheet__title">
          Install InsighteCase again
        </h2>
        <p className="app-version-sheet__lead">
          {formatVersionNoticeLead(embeddedReleaseLabel, remoteReleaseLabel)}
        </p>
        <ol className="app-version-sheet__steps app-version-sheet__steps--compact">
          <li>
            <span className="app-version-sheet__step-num">1.</span>
            {removeLine}
          </li>
          <li>
            <span className="app-version-sheet__step-num">2.</span>
            {isIos ? (
              <>
                <button type="button" className="app-version-btn app-version-btn--primary app-version-btn--inline" onClick={handleInstall}>
                  Open InsighteCase
                </button>
                <p className="app-version-sheet__step-hint">Then tap Share → Add to Home Screen → Add.</p>
              </>
            ) : (
              <button type="button" className="app-version-btn app-version-btn--primary app-version-btn--inline" onClick={handleInstall}>
                Install InsighteCase
              </button>
            )}
          </li>
        </ol>
        <button type="button" className="app-version-notice__later" onClick={() => void handleCopy()}>
          Copy link
        </button>
        {copyNote ? <p className="app-version-sheet__note">{copyNote}</p> : null}
        <div className="app-version-sheet__actions">
          <button type="button" className="app-version-btn app-version-btn--ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
