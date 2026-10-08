import { useCallback, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  buildIosSafariOpenUrl,
  detectReinstallPlatform,
  formatVersionNoticeLead,
  getReinstallSteps,
} from '../../lib/appVersionUpdate.js'
import { getCanonicalPortalUrl } from '../../lib/canonicalAppUrl.js'
import { usePortalInstall } from '../../context/usePortalInstall.js'
import './app-version-notice.css'

async function copyText(url) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(url)
      return true
    }
  } catch {
    // fall through
  }
  return false
}

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
  const { canNativeInstall, promptInstall } = usePortalInstall()
  const platform = detectReinstallPlatform()
  const steps = getReinstallSteps(platform, { portalUrl, appName })
  const [copyNote, setCopyNote] = useState('')

  const handleCopy = useCallback(async () => {
    const url = portalUrl || getCanonicalPortalUrl(portalId)
    const ok = await copyText(url)
    setCopyNote(ok ? 'Link copied.' : `Copy this link: ${url}`)
  }, [portalId, portalUrl])

  const handleOpenSafari = useCallback(() => {
    const url = portalUrl || getCanonicalPortalUrl(portalId)
    const safariUrl = buildIosSafariOpenUrl(url)
    const opened = window.open(safariUrl, '_blank')
    if (!opened) {
      void handleCopy()
      setCopyNote((prev) => prev || 'Link copied — paste it in Safari.')
    }
  }, [handleCopy, portalId, portalUrl])

  const handleOpenBrowser = useCallback(() => {
    const url = portalUrl || getCanonicalPortalUrl(portalId)
    const opened = window.open(url, '_blank', 'noopener,noreferrer')
    if (!opened) void handleCopy()
  }, [handleCopy, portalId, portalUrl])

  const handleNativeInstall = useCallback(async () => {
    const result = await promptInstall()
    if (result?.outcome === 'accepted') {
      onClose()
    }
  }, [onClose, promptInstall])

  const showInstallNow =
    canNativeInstall && (platform === 'android' || platform === 'android-edge' || platform === 'desktop' || platform === 'desktop-edge')

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
          Re-add the InsighteCase shortcut
        </h2>
        <p className="app-version-sheet__lead">
          {formatVersionNoticeLead(embeddedReleaseLabel, remoteReleaseLabel)} Follow these steps to
          refresh the web app on your home screen or desktop.
        </p>
        <p className="app-version-sheet__url-line">
          <a className="app-version-sheet__url" href={portalUrl} target="_blank" rel="noopener noreferrer">
            {portalUrl}
          </a>
        </p>
        {showInstallNow ? (
          <div className="app-version-sheet__actions app-version-sheet__actions--top">
            <button type="button" className="app-version-btn app-version-btn--primary" onClick={() => void handleNativeInstall()}>
              Install now
            </button>
          </div>
        ) : null}
        <ol className="app-version-sheet__steps">
            {steps.map((step, index) => {
              if (step.kind === 'action') {
                const onAction =
                  step.action === 'copy'
                    ? () => void handleCopy()
                    : step.action === 'open_safari'
                      ? handleOpenSafari
                      : handleOpenBrowser
                return (
                  <li key={step.id}>
                    <span className="app-version-sheet__step-num">{index + 1}.</span>
                    <button type="button" className="app-version-btn app-version-btn--secondary app-version-btn--inline" onClick={onAction}>
                      {step.label}
                    </button>
                    {step.hint ? <p className="app-version-sheet__step-hint">{step.hint}</p> : null}
                  </li>
                )
              }
              return (
                <li key={step.id}>
                  <span className="app-version-sheet__step-num">{index + 1}.</span>
                  {step.text}
                </li>
              )
            })}
        </ol>
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
