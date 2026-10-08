import { useCallback, useMemo, useState } from 'react'
import { isStandaloneDisplay } from '../../lib/portalPwa.js'
import { refreshApp } from '../../lib/pwaUpdate.js'
import { clearPwaStaleHint } from '../../lib/pwaStaleRecovery.js'
import {
  formatVersionNoticeLead,
  getEmbeddedReleaseLabel,
} from '../../lib/appVersionUpdate.js'
import { getCanonicalPortalUrl } from '../../lib/canonicalAppUrl.js'
import {
  copyText,
  detectReinstallPlatform,
  getReinstallUrl,
  isIosPlatform,
  launchReinstallInBrowser,
} from '../../lib/pwaReinstall.js'
import { useAppVersionNotice } from '../../hooks/useAppVersionNotice.js'
import { useReinstallLanding } from '../../hooks/useReinstallLanding.js'
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
  const hook = useAppVersionNotice()
  const reinstallLanding = useReinstallLanding()
  const embeddedReleaseLabel =
    testOverrides?.embeddedReleaseLabel ?? hook.embeddedReleaseLabel ?? getEmbeddedReleaseLabel()
  const remoteReleaseLabel = testOverrides?.remoteReleaseLabel ?? hook.remoteReleaseLabel
  const notice = testOverrides?.notice ?? hook.notice
  const dismissForSession = hook.dismissForSession

  const standalone = testOverrides?.standalone ?? isStandaloneDisplay()
  const portalUrl = useMemo(() => getCanonicalPortalUrl(portalId), [portalId])
  const platform = detectReinstallPlatform()
  const ios = isIosPlatform(platform)
  const [note, setNote] = useState('')
  const [dismissedKey, setDismissedKey] = useState(null)

  const reinstallFallback = Boolean(notice.reinstallFallback) && standalone

  const handleDismiss = useCallback(() => {
    setDismissedKey(notice.buildKey ?? 'unknown')
    dismissForSession()
    clearPwaStaleHint()
  }, [dismissForSession, notice.buildKey])

  const handleCopy = useCallback(async () => {
    const url = reinstallFallback ? getReinstallUrl(portalId) : portalUrl
    const ok = await copyText(url)
    setNote(ok ? 'Link copied.' : `Copy this link: ${url}`)
  }, [portalId, portalUrl, reinstallFallback])

  const handleReload = useCallback(() => {
    clearPwaStaleHint()
    void refreshApp()
  }, [])

  const handleReinstall = useCallback(() => {
    launchReinstallInBrowser(platform, portalId)
    setNote(
      `Opening ${ios ? 'Safari' : 'your browser'}… If nothing opens, tap Copy link and paste it into Chrome, Edge or Safari.`,
    )
  }, [ios, platform, portalId])

  // On the ?reinstall=1 landing the install dialog is the only action on screen.
  const dismissed = dismissedKey !== null && dismissedKey === (notice.buildKey ?? 'unknown')
  if (!notice.show || dismissed || reinstallLanding.active) return null

  const lead = remoteReleaseLabel
    ? formatVersionNoticeLead(embeddedReleaseLabel, remoteReleaseLabel)
    : 'A newer web build is available.'
  const detail = reinstallFallback
    ? 'This app didn’t update by itself, so it needs a quick reinstall.'
    : remoteReleaseLabel
      ? 'InsighteCase refreshes automatically when you open it.'
      : 'Reload if anything looks stuck.'

  return (
    <div
      className={`app-version-notice app-version-notice--${variant}`}
      role="region"
      aria-label="App update available"
    >
      <div className="app-version-notice__copy">
        <strong className="app-version-notice__title">A new version of InsighteCase is ready.</strong>
        <p className="app-version-notice__lead">
          {lead} {detail}
        </p>
        <p className="app-version-notice__url-line">
          <a className="app-version-notice__url" href={portalUrl} target="_blank" rel="noopener noreferrer">
            {portalUrl}
          </a>
        </p>
      </div>
      <div className="app-version-notice__actions">
        {reinstallFallback ? (
          <button
            type="button"
            className="app-version-btn app-version-btn--primary"
            onClick={handleReinstall}
            aria-describedby={note ? undefined : 'app-version-reinstall-hint'}
          >
            {ios ? 'Open InsighteCase' : 'Install InsighteCase'}
          </button>
        ) : !standalone ? (
          <button type="button" className="app-version-btn app-version-btn--primary" onClick={handleReload}>
            Reload to update
          </button>
        ) : null}
        <div className="app-version-notice__minor">
          <button type="button" className="app-version-notice__later" onClick={() => void handleCopy()}>
            Copy link
          </button>
          <button type="button" className="app-version-notice__later" onClick={handleDismiss}>
            Later
          </button>
        </div>
      </div>
      {reinstallFallback && !note ? (
        <p id="app-version-reinstall-hint" className="app-version-notice__hint">
          {ios
            ? 'Opens InsighteCase in Safari, where you can add it to your home screen again.'
            : 'Opens InsighteCase in your browser, where you can install the new version.'}
        </p>
      ) : null}
      {note ? (
        <p className="app-version-notice__note" role="status">
          {note}
        </p>
      ) : null}
    </div>
  )
}
