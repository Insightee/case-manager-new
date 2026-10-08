import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  detectReinstallPlatform,
  getBrowserMenuInstallFallback,
  hasInstalledRelatedPwa,
  isReinstallLanding,
} from '../../lib/pwaReinstall.js'
import './pwa-reinstall-landing.css'

/**
 * Shown on any route when ?reinstall=1 — captures beforeinstallprompt for one-tap install.
 */
export function PwaReinstallLanding() {
  const [searchParams] = useSearchParams()
  const active = isReinstallLanding(searchParams)
  const platform = detectReinstallPlatform()
  const isIos = platform.startsWith('ios')

  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [oldAppLikely, setOldAppLikely] = useState(false)
  const [awaitingPrompt, setAwaitingPrompt] = useState(true)
  const [installOutcome, setInstallOutcome] = useState('')

  useEffect(() => {
    if (!active) return undefined

    let cancelled = false
    void hasInstalledRelatedPwa().then((yes) => {
      if (!cancelled) setOldAppLikely(yes)
    })

    function onBeforeInstallPrompt(event) {
      event.preventDefault()
      setDeferredPrompt(event)
      setAwaitingPrompt(false)
    }

    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
    const timer = window.setTimeout(() => setAwaitingPrompt(false), 3000)

    return () => {
      cancelled = true
      window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
      window.clearTimeout(timer)
    }
  }, [active])

  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return
    deferredPrompt.prompt()
    const choice = await deferredPrompt.userChoice
    setDeferredPrompt(null)
    setInstallOutcome(choice.outcome === 'accepted' ? 'Shortcut added — open it from your home screen or desktop.' : '')
  }, [deferredPrompt])

  if (!active) return null

  if (isIos) {
    return (
      <aside className="pwa-reinstall-landing" role="region" aria-label="Add InsighteCase to home screen">
        <p className="pwa-reinstall-landing__title">Add InsighteCase to your home screen</p>
        <p className="pwa-reinstall-landing__hint">Tap Share → Add to Home Screen → Add.</p>
      </aside>
    )
  }

  const showBlockedHint = !deferredPrompt && !awaitingPrompt && (oldAppLikely || platform.startsWith('android') || platform.startsWith('desktop'))

  return (
    <aside className="pwa-reinstall-landing" role="region" aria-label="Install InsighteCase">
      <p className="pwa-reinstall-landing__title">Install InsighteCase</p>
      <button
        type="button"
        className="pwa-reinstall-landing__install app-version-btn app-version-btn--primary"
        disabled={!deferredPrompt}
        onClick={() => void handleInstall()}
      >
        Install InsighteCase
      </button>
      {awaitingPrompt && !deferredPrompt ? (
        <p className="pwa-reinstall-landing__hint">Preparing install…</p>
      ) : null}
      {showBlockedHint ? (
        <p className="pwa-reinstall-landing__hint">
          Remove the old InsighteCase app first, then tap Install again. Or use {getBrowserMenuInstallFallback(platform)}.
        </p>
      ) : null}
      {installOutcome ? <p className="pwa-reinstall-landing__success">{installOutcome}</p> : null}
    </aside>
  )
}
