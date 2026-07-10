import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { SkipLink } from '../components/shared/SkipLink.jsx'
import { RouteLoading } from '../components/shared/RouteLoading.jsx'
import { usePageMeta } from '../hooks/usePageMeta.js'
import { getTokens } from '../lib/apiClient.js'
import {
  formatLoginErrorMessage,
  portalHomePath,
  sessionMatchesLoginPage,
  SIGN_IN_PATH,
} from '../lib/portalLogin.js'

const DEMO_PASSWORD = 'demo123'
const REMEMBER_ME_KEY = 'insightcase_remember_me'

/** @typedef {{ email: string, label: string, hint?: string }} DemoAccount */
/** @typedef {{ title: string, accounts: DemoAccount[] }} DemoGroup */

const PORTALS = [
  {
    id: 'therapist',
    label: 'Therapist',
    cardTitle: 'I am a Therapist',
    cardSubtitle: 'For attendance, session notes, and managing your clients',
    cardAction: 'Open Therapist Dashboard',
    iconSrc: '/branding/portal-therapist.png',
    subtitle: 'Daily logs, cases, reports, and invoices.',
    placeholder: 'therapist@demo.com',
    demos: [{ email: 'therapist@demo.com', label: 'Therapist', hint: 'Therapist home' }],
  },
  {
    id: 'parent',
    label: 'Client',
    cardTitle: 'I am a Parent / Client',
    cardSubtitle: 'For child updates, reports, IEP and billing',
    cardAction: 'Open Parent Dashboard',
    iconSrc: '/branding/portal-parent.png',
    subtitle: 'Approved reports, IEP acknowledgements, and billing.',
    placeholder: 'parent@demo.com',
    demos: [{ email: 'parent@demo.com', label: 'Parent / Guardian', hint: 'Client portal' }],
  },
  {
    id: 'admin',
    label: 'Admin',
    cardTitle: 'I am an Insighte Admin',
    cardSubtitle: 'For Admins, HR , Tech team',
    cardSubtitleSmall: true,
    cardAction: 'Open Admin Dashboard',
    iconSrc: '/branding/portal-admin.png',
    subtitle: 'Case managers, module admins, finance, and HR.',
    placeholder: 'moduleadmin@demo.com',
    demoGroups: [
      {
        title: 'Platform & modules',
        accounts: [
          { email: 'superadmin@demo.com', label: 'Super Admin', hint: 'Full admin home' },
          { email: 'moduleadmin@demo.com', label: 'Module Admin', hint: 'Homecare + shadow + billing' },
          { email: 'admin@demo.com', label: 'Programme Admin', hint: 'Homecare write only' },
          { email: 'support@demo.com', label: 'Support Admin', hint: 'Homecare + billing' },
        ],
      },
      {
        title: 'Case managers',
        accounts: [
          { email: 'casemanager@demo.com', label: 'Case Manager', hint: 'My caseload · homecare + shadow' },
          { email: 'shadowcm@demo.com', label: 'CM · Shadow caseload', hint: 'My caseload · shadow only' },
          { email: 'viewonly@demo.com', label: 'CM · View only', hint: 'Read-only · no mutations' },
        ],
      },
      {
        title: 'Finance',
        accounts: [{ email: 'finance@demo.com', label: 'Finance', hint: 'Invoices & payouts' }],
      },
      {
        title: 'People & HR',
        accounts: [{ email: 'hr@demo.com', label: 'HR', hint: 'People, leave, memos' }],
      },
    ],
  },
]

function flattenDemos(portal) {
  if (portal.demoGroups) {
    return portal.demoGroups.flatMap((g) => g.accounts)
  }
  return portal.demos ?? []
}

function InsighteLogo({ className = '' }) {
  return (
    <img
      src="/branding/insighte-logo.png"
      alt="Insighte"
      className={className ? `login-insighte-logo ${className}` : 'login-insighte-logo'}
      height={44}
      width={180}
    />
  )
}

function formatLoginError(err) {
  const msg = err?.message || ''
  if (/timed out/i.test(msg)) {
    const hostname = typeof window !== 'undefined' ? window.location.hostname : ''
    const localDev = hostname === 'localhost' || hostname === '127.0.0.1'
    if (localDev) {
      return `${msg} Ensure uvicorn is running on port 8000, or use an empty VITE_API_URL with npm run dev.`
    }
    return `${msg} The API may be unreachable — check your connection or contact your administrator.`
  }
  return formatLoginErrorMessage(msg)
}

export function LoginPage({ portalType }) {
  const { login, logout, updateLoginPortal, user, loading, selectedPortal, reload } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const gateRunRef = useRef(0)
  const sessionRestoreAttemptsRef = useRef(0)

  const [portalGateReady, setPortalGateReady] = useState(false)
  const [rememberMe, setRememberMe] = useState(() => {
    const saved = localStorage.getItem(REMEMBER_ME_KEY)
    if (saved === '1') return true
    if (saved === '0') return false
    return portalType === 'parent' || portalType === 'therapist'
  })

  const queryParams = useMemo(() => {
    return new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '')
  }, [])
  const isDemoMode = useMemo(() => {
    return queryParams.get('demo') === 'true' || queryParams.get('demo') === '1'
  }, [queryParams])

  const initialPortal = useMemo(() => {
    if (portalType && portalType !== 'dev') return portalType
    return 'therapist'
  }, [portalType])

  const [portal, setPortal] = useState(initialPortal)
  const [email, setEmail] = useState(() => {
    if (portalType && portalType !== 'dev') {
      if (isDemoMode) {
        const next = PORTALS.find((p) => p.id === portalType)
        const first = next ? flattenDemos(next)[0] : null
        return first ? first.email : ''
      }
      return ''
    }
    return 'therapist@demo.com'
  })
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [selectedDemoEmail, setSelectedDemoEmail] = useState('')

  useEffect(() => {
    const runId = ++gateRunRef.current
    if (loading) {
      setPortalGateReady(false)
      return undefined
    }

    let cancelled = false

    async function runPortalGate() {
      const tokens = getTokens()
      const hasSession = Boolean(tokens.access || tokens.refresh)

      if (!portalType) {
        if (hasSession || user) logout()
        if (!cancelled && runId === gateRunRef.current) setPortalGateReady(true)
        return
      }

      if (portalType === 'dev') {
        if (!cancelled && runId === gateRunRef.current) setPortalGateReady(true)
        return
      }

      if (hasSession && !user) {
        sessionRestoreAttemptsRef.current += 1
        if (sessionRestoreAttemptsRef.current >= 2) {
          logout()
          sessionRestoreAttemptsRef.current = 0
          if (!cancelled && runId === gateRunRef.current) setPortalGateReady(true)
          return
        }
        await reload()
        return
      }

      sessionRestoreAttemptsRef.current = 0

      if (user && sessionMatchesLoginPage(user, selectedPortal, portalType)) {
        navigate(portalHomePath(user), { replace: true })
        return
      }

      if (hasSession || user) logout()

      if (!cancelled && runId === gateRunRef.current) setPortalGateReady(true)
    }

    setPortalGateReady(false)
    void runPortalGate()

    return () => {
      cancelled = true
    }
  }, [loading, user, selectedPortal, portalType, logout, reload, navigate])

  // Sync login portal with context, without updating local component state
  useEffect(() => {
    if (portalType && portalType !== 'dev') {
      updateLoginPortal(portalType)
    } else {
      updateLoginPortal(null)
    }
  }, [portalType, updateLoginPortal])

  useEffect(() => {
    const message = location.state?.loginError
    if (!message) return
    setError(message)
    navigate(location.pathname + location.search, { replace: true, state: {} })
  }, [location.state?.loginError, location.pathname, location.search, navigate])

  const currentPortalId = useMemo(() => {
    if (portalType && portalType !== 'dev') return portalType
    return portal
  }, [portalType, portal])

  const active = useMemo(() => PORTALS.find((p) => p.id === currentPortalId) ?? PORTALS[0], [currentPortalId])
  const activeDemos = useMemo(() => flattenDemos(active), [active])

  usePageMeta({
    title: 'Sign in',
    description: `Sign in to the InsighteCase ${active.label.toLowerCase()} portal.`,
  })

  function selectPortal(id) {
    setPortal(id)
    setError('')
    setSelectedDemoEmail('')
    const next = PORTALS.find((p) => p.id === id)
    const first = next ? flattenDemos(next)[0] : null
    if (first) setEmail(first.email)
  }

  async function signInDemo(demoEmail) {
    setSelectedDemoEmail(demoEmail)
    setEmail(demoEmail)
    setPassword(DEMO_PASSWORD)
    setError('')
    setSubmitting(true)
    try {
      if (portalType && portalType !== 'dev') {
        updateLoginPortal(portalType)
      } else {
        updateLoginPortal(portal)
      }
      await login(
        demoEmail.trim().toLowerCase(),
        DEMO_PASSWORD,
        portalType === 'dev' ? null : currentPortalId,
        rememberMe,
      )
      navigate('/')
    } catch (err) {
      setError(formatLoginError(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      if (portalType && portalType !== 'dev') {
        updateLoginPortal(portalType)
      } else {
        updateLoginPortal(portal)
      }
      await login(
        email.trim().toLowerCase(),
        password,
        portalType === 'dev' ? null : currentPortalId,
        rememberMe,
      )
      navigate('/')
    } catch (err) {
      setError(formatLoginError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const isStaffPortal = currentPortalId === 'admin'

  function demoButtonClass(demoEmail) {
    return `login-demo-btn${selectedDemoEmail === demoEmail ? ' is-selected' : ''}`
  }

  if (loading || !portalGateReady) {
    return (
      <div className="login-page">
        <RouteLoading />
      </div>
    )
  }

  // 1. Selector Gateway Page (no portalType specified)
  if (!portalType) {
    return (
      <div className="login-page">
        <SkipLink />
        <div className="login-shell">
          <section className="login-card" style={{ maxWidth: '800px', display: 'flex', flexDirection: 'column', gap: '2rem', padding: '3rem' }}>
            <header className="login-header login-header--gateway">
              <InsighteLogo />
              <h1 className="login-title login-title--gateway">Welcome</h1>
              <p className="login-sub login-sub--gateway">Please select your portal to sign in to your dashboard</p>
            </header>

            <div className="portal-selection-grid">
              {PORTALS.map((p) => {
                const route =
                  p.id === 'parent'
                    ? SIGN_IN_PATH.parent
                    : p.id === 'therapist'
                      ? SIGN_IN_PATH.therapist
                      : SIGN_IN_PATH.admin
                return (
                  <Link
                    key={p.id}
                    to={route}
                    className="portal-selection-card"
                  >
                    <img
                      src={p.iconSrc}
                      alt=""
                      className="portal-card-icon"
                      width={56}
                      height={56}
                      aria-hidden="true"
                    />
                    <h3 className="portal-card-title">{p.cardTitle}</h3>
                    <p className={`portal-card-desc${p.cardSubtitleSmall ? ' portal-card-desc--small' : ''}`}>
                      {p.cardSubtitle}
                    </p>

                    <span className="portal-card-action">
                      {p.cardAction} <span aria-hidden="true">→</span>
                    </span>
                  </Link>
                )
              })}
            </div>
          </section>
        </div>
      </div>
    )
  }

  // 2. Portal-Specific Form or Developer/Testing Page
  return (
    <div className="login-page">
      <SkipLink />
      <div className="login-shell">
        <section className={`login-card ${portalType === 'dev' ? '' : 'login-card--single'}`}>
          <main id="main-content" className="login-main" tabIndex={-1}>
            <header className="login-header">
              <InsighteLogo className="login-insighte-logo--form" />
              <h1 className="login-title">{active.label} portal</h1>
              <p className="login-sub">{active.subtitle}</p>
            </header>

            {portalType === 'dev' && (
              <div className="portal-tabs portal-tabs--three" role="tablist" aria-label="Select portal">
                {PORTALS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    role="tab"
                    aria-selected={portal === p.id}
                    className={portal === p.id ? 'is-active' : ''}
                    onClick={() => selectPortal(p.id)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            )}

            <form onSubmit={handleSubmit} className="login-form">
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={active.placeholder}
                  autoComplete="username"
                  required
                />
              </label>
              <label>
                Password
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    style={{ width: '100%', paddingRight: '50px' }}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute',
                      right: '10px',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: '#4f46e5',
                      padding: '4px 8px',
                    }}
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
              </label>
              {portalType && portalType !== 'dev' ? (
                <label
                  className="login-remember"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem' }}
                >
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => {
                      const checked = e.target.checked
                      setRememberMe(checked)
                      localStorage.setItem(REMEMBER_ME_KEY, checked ? '1' : '0')
                    }}
                  />
                  Keep me signed in
                </label>
              ) : null}
              <p className="login-sub" style={{ marginTop: '-0.5rem', textAlign: 'right' }}>
                <Link
                  to={
                    portalType && portalType !== 'dev'
                      ? `/forgot-password?portal=${encodeURIComponent(currentPortalId)}`
                      : '/forgot-password?portal=admin'
                  }
                >
                  Forgot password?
                </Link>
              </p>
              {error ? (
                <p className="login-error" role="alert">
                  {error}
                </p>
              ) : null}
              <button type="submit" className="login-submit" disabled={submitting} aria-busy={submitting}>
                {submitting ? 'Signing in…' : 'Sign in'}
              </button>
            </form>

            {(portalType === 'dev' || isDemoMode) && (
              <div className={`login-hint ${isStaffPortal ? 'login-hint--admin' : ''}`}>
                <p className="login-hint__label">
                  Demo password: <code>{DEMO_PASSWORD}</code>. Pick a role below to sign in instantly.
                </p>
                {active.demoGroups ? (
                  <div className="login-demo-groups">
                    {active.demoGroups.map((group) => (
                      <section key={group.title} className="login-demo-group" aria-labelledby={`demo-${group.title}`}>
                        <h3 id={`demo-${group.title}`} className="login-demo-group__title">
                          {group.title}
                        </h3>
                        <ul className="login-demo-list">
                          {group.accounts.map((d) => (
                            <li key={d.email}>
                              <button
                                type="button"
                                className={demoButtonClass(d.email)}
                                disabled={submitting}
                                onClick={() => signInDemo(d.email)}
                              >
                                <span className="login-demo-btn__text">
                                  <span className="login-demo-btn__role">{d.label}</span>
                                  {d.hint ? <span className="login-demo-btn__hint">{d.hint}</span> : null}
                                </span>
                                <code>{d.email}</code>
                              </button>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ))}
                  </div>
                ) : (
                  <ul className="login-demo-list">
                    {activeDemos.map((d) => (
                      <li key={d.email}>
                        <button
                          type="button"
                          className={demoButtonClass(d.email)}
                          disabled={submitting}
                          onClick={() => signInDemo(d.email)}
                        >
                          <span className="login-demo-btn__text">
                            <span className="login-demo-btn__role">{d.label}</span>
                            {d.hint ? <span className="login-demo-btn__hint">{d.hint}</span> : null}
                          </span>
                          <code>{d.email}</code>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </main>

          {portalType === 'dev' && (
            <aside className="login-aside" aria-label="Platform highlights">
              <p className="login-aside__tag">Case-centric care</p>
              <h2>One platform for your whole team</h2>
              <ul className="login-aside__list">
                {PORTALS.map((p) => (
                  <li key={p.id} className={portal === p.id ? 'is-active' : ''}>
                    {p.label}
                  </li>
                ))}
              </ul>
              {isStaffPortal ? (
                <p className="login-aside__note">
                  Finance, HR, and case managers all use the admin portal with role-based navigation.
                </p>
              ) : null}
            </aside>
          )}
        </section>
      </div>
    </div>
  )
}
