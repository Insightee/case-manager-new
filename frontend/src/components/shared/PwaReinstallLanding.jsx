import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useReinstallLanding } from '../../hooks/useReinstallLanding.js'
import {
  getDeferredInstallPrompt,
  promptDeferredInstall,
  subscribeInstallPrompt,
  wasInstalledThisVisit,
} from '../../lib/installPromptStore.js'
import { isStandaloneDisplay } from '../../lib/portalPwa.js'
import {
  clearReinstallLanding,
  copyText,
  detectReinstallPlatform,
  getInstalledMessage,
  getManualAddHint,
  getManualAddLine,
  getPortalAppName,
  getReinstallUrl,
  getRemoveAppOneLiner,
  stripReinstallParamFromAddressBar,
  supportsOneTapInstall,
} from '../../lib/pwaReinstall.js'
import './app-version-notice.css'
import './pwa-reinstall-landing.css'

const PROMPT_WAIT_MS = 3000

/**
 * Browser landing for ?reinstall=1 (opened from the old installed app).
 * Step 1: remove the old app. Step 2: one-tap install (Chrome/Edge) or Share > Add to Home Screen (Safari).
 */
export function PwaReinstallLanding() {
  const { active, portal } = useReinstallLanding()
  if (!active) return null
  return <PwaReinstallLandingDialog portal={portal} />
}

function useInstallPromptState() {
  const [state, setState] = useState(() => ({
    canPrompt: Boolean(getDeferredInstallPrompt()),
    installed: wasInstalledThisVisit(),
  }))
  useEffect(() => {
    const sync = () =>
      setState({ canPrompt: Boolean(getDeferredInstallPrompt()), installed: wasInstalledThisVisit() })
    sync()
    return subscribeInstallPrompt(sync)
  }, [])
  return state
}

/** @param {{ portal: 'parent' | 'therapist' | 'admin' | null }} props */
function PwaReinstallLandingDialog({ portal }) {
  const platform = detectReinstallPlatform()
  const appName = getPortalAppName(portal)
  const oneTap = supportsOneTapInstall(platform)
  const insideOldApp = isStandaloneDisplay()
  const { canPrompt, installed } = useInstallPromptState()
  const [waited, setWaited] = useState(false)
  const [dismissedPrompt, setDismissedPrompt] = useState(false)
  const [copyNote, setCopyNote] = useState('')
  const panelRef = useRef(null)

  useEffect(() => {
    const timer = window.setTimeout(() => setWaited(true), PROMPT_WAIT_MS)
    return () => window.clearTimeout(timer)
  }, [])

  useEffect(() => {
    // Keep the success message on screen; just tidy the address bar. Done clears the flag.
    if (installed) stripReinstallParamFromAddressBar()
  }, [installed])

  const close = useCallback(() => {
    clearReinstallLanding()
  }, [])

  useEffect(() => {
    function onKey(event) {
      if (event.key === 'Escape') close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [close])

  useEffect(() => {
    // Move focus into the dialog so screen readers announce it; buttons stay in natural tab order.
    panelRef.current?.focus?.({ preventScroll: true })
  }, [])

  const handleInstall = useCallback(async () => {
    const { outcome } = await promptDeferredInstall()
    if (outcome === 'dismissed') setDismissedPrompt(true)
  }, [])

  const handleRetry = useCallback(() => {
    // User-initiated only: the browser re-checks installability on a fresh load.
    window.location.reload()
  }, [])

  const handleCopy = useCallback(async () => {
    const url = getReinstallUrl(portal)
    const ok = await copyText(url)
    setCopyNote(ok ? 'Link copied.' : `Copy this link: ${url}`)
  }, [portal])

  let body
  if (installed) {
    body = (
      <>
        <h2 id="pwa-reinstall-title" className="app-version-sheet__title">
          You’re all set
        </h2>
        <p className="pwa-reinstall-landing__success" role="status">
          {getInstalledMessage(platform)}
        </p>
        <div className="app-version-sheet__actions">
          <button type="button" className="app-version-btn app-version-btn--primary" onClick={close}>
            Done
          </button>
        </div>
      </>
    )
  } else if (insideOldApp) {
    body = (
      <>
        <h2 id="pwa-reinstall-title" className="app-version-sheet__title">
          Open this in your browser
        </h2>
        <p className="app-version-sheet__lead">
          This page opened inside the old app. Copy the link and paste it into a Chrome, Edge or Safari tab.
        </p>
        <div className="app-version-sheet__actions">
          <button type="button" className="app-version-btn app-version-btn--primary" onClick={() => void handleCopy()}>
            Copy link
          </button>
          {copyNote ? (
            <p className="app-version-sheet__note" role="status">
              {copyNote}
            </p>
          ) : null}
          <button type="button" className="app-version-notice__later" onClick={close}>
            Not now
          </button>
        </div>
      </>
    )
  } else {
    let stepTwo
    if (oneTap && canPrompt) {
      stepTwo = (
        <button
          type="button"
          className="app-version-btn app-version-btn--primary pwa-reinstall-landing__cta"
          onClick={() => void handleInstall()}
        >
          Install InsighteCase
        </button>
      )
    } else if (oneTap && !waited && !dismissedPrompt) {
      stepTwo = (
        <>
          <button type="button" className="app-version-btn app-version-btn--primary pwa-reinstall-landing__cta" disabled>
            Install InsighteCase
          </button>
          <p className="app-version-sheet__step-hint" role="status">
            Getting the install ready…
          </p>
        </>
      )
    } else if (oneTap) {
      stepTwo = (
        <>
          <p className="pwa-reinstall-landing__step-text">
            {dismissedPrompt
              ? 'Install was cancelled. Tap Try again when you are ready.'
              : 'Install isn’t ready yet. Make sure the old app is removed (step 1), then tap Try again.'}
          </p>
          <button
            type="button"
            className="app-version-btn app-version-btn--primary pwa-reinstall-landing__cta"
            onClick={handleRetry}
          >
            Try again
          </button>
        </>
      )
    } else {
      const hint = getManualAddHint(platform)
      stepTwo = (
        <>
          <p className="pwa-reinstall-landing__step-text">{getManualAddLine(platform)}</p>
          {hint ? <p className="app-version-sheet__step-hint">{hint}</p> : null}
        </>
      )
    }

    body = (
      <>
        <h2 id="pwa-reinstall-title" className="app-version-sheet__title">
          Install the new InsighteCase
        </h2>
        <ol className="pwa-reinstall-landing__steps">
          <li>
            <span className="pwa-reinstall-landing__num" aria-hidden="true">
              1
            </span>
            <div className="pwa-reinstall-landing__step-body">
              <p className="pwa-reinstall-landing__step-label">Remove the old app</p>
              <p className="pwa-reinstall-landing__step-text">{getRemoveAppOneLiner(platform, appName)}</p>
            </div>
          </li>
          <li>
            <span className="pwa-reinstall-landing__num" aria-hidden="true">
              2
            </span>
            <div className="pwa-reinstall-landing__step-body">
              <p className="pwa-reinstall-landing__step-label">
                {oneTap ? 'Install it again' : platform === 'mac-safari' ? 'Add it to your Dock' : 'Add it to your home screen'}
              </p>
              {stepTwo}
            </div>
          </li>
        </ol>
        <div className="app-version-sheet__actions">
          <button
            type="button"
            className="app-version-notice__later pwa-reinstall-landing__later"
            onClick={close}
          >
            Not now
          </button>
        </div>
      </>
    )
  }

  return createPortal(
    <div className="app-version-sheet pwa-reinstall-landing" role="presentation">
      <div
        className="app-version-sheet__panel pwa-reinstall-landing__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pwa-reinstall-title"
        data-testid="pwa-reinstall-landing"
        tabIndex={-1}
        ref={panelRef}
      >
        {body}
      </div>
    </div>,
    document.body,
  )
}
