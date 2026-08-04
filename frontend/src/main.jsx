import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import './index.css'
import './styles/forest-light-theme.css'
import App from './App.jsx'

// Stale production service workers on localhost cause blank screens — clear in dev only.
if (import.meta.env.DEV && typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
  void navigator.serviceWorker.getRegistrations().then((regs) => {
    regs.forEach((reg) => void reg.unregister())
  })
} else if (!import.meta.env.DEV) {
  registerSW({ immediate: true })
}

// Canonical host: apex insighte.org 308-redirects and breaks credentialed /api PATCH preflights.
if (typeof window !== 'undefined' && window.location.hostname === 'insighte.org') {
  const target = `https://www.insighte.org${window.location.pathname}${window.location.search}${window.location.hash}`
  window.location.replace(target)
} else {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
