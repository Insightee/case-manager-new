import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { SkipLink } from '../components/shared/SkipLink.jsx'
import { usePageMeta } from '../hooks/usePageMeta.js'
import { formatLoginErrorMessage } from '../lib/portalLogin.js'

const DEMO_PASSWORD = 'demo123'

/** @typedef {{ email: string, label: string, hint?: string }} DemoAccount */
/** @typedef {{ title: string, accounts: DemoAccount[] }} DemoGroup */

const PORTALS = [
  {
    id: 'therapist',
    label: 'Therapist',
    subtitle: 'Daily logs, cases, reports, and invoices.',
    placeholder: 'therapist@demo.com',
    demos: [{ email: 'therapist@demo.com', label: 'Therapist', hint: 'Therapist home' }],
  },
  {
    id: 'parent',
    label: 'Client',
    subtitle: 'Approved reports, IEP acknowledgements, and billing.',
    placeholder: 'parent@demo.com',
    demos: [{ email: 'parent@demo.com', label: 'Parent / Guardian', hint: 'Client portal' }],
  },
  {
    id: 'admin',
    label: 'Staff',
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
  const { login, updateLoginPortal } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

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
      await login(demoEmail.trim().toLowerCase(), DEMO_PASSWORD, portalType === 'dev' ? null : currentPortalId)
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
      await login(email.trim().toLowerCase(), password, portalType === 'dev' ? null : currentPortalId)
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

  // 1. Selector Gateway Page (no portalType specified)
  if (!portalType) {
    return (
      <div className="login-page">
        <SkipLink />
        <div className="login-shell">
          <section className="login-card" style={{ maxWidth: '800px', display: 'flex', flexDirection: 'column', gap: '2rem', padding: '3rem' }}>
            <header className="login-header" style={{ textAlign: 'center', marginBottom: '1rem' }}>
              <p className="login-brand" style={{ fontSize: '1.5rem', fontWeight: '800', letterSpacing: '-0.025em', color: 'var(--color-primary, #6366f1)', marginBottom: '0.5rem' }}>InsighteCase</p>
              <h1 className="login-title" style={{ fontSize: '2.25rem', fontWeight: '800', tracking: '-0.025em', margin: '0' }}>Welcome to InsighteCase</h1>
              <p className="login-sub" style={{ fontSize: '1rem', color: 'var(--color-text-muted, #6b7280)', marginTop: '0.5rem' }}>Please select your portal to sign in to your dashboard</p>
            </header>

            <div className="portal-selection-grid" style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '1.5rem',
              width: '100%'
            }}>
              {PORTALS.map((p) => {
                const route = p.id === 'parent' ? '/clientlogin' : p.id === 'therapist' ? '/therapistlogin' : '/stafflogin'
                return (
                  <Link
                    key={p.id}
                    to={route}
                    className="portal-selection-card"
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      padding: '2rem 1.5rem',
                      borderRadius: '16px',
                      backgroundColor: 'rgba(255, 255, 255, 0.05)',
                      backdropFilter: 'blur(16px)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      textDecoration: 'none',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      color: 'inherit',
                      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'translateY(-6px)'
                      e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.4)'
                      e.currentTarget.style.backgroundColor = 'rgba(99, 102, 241, 0.08)'
                      e.currentTarget.style.boxShadow = '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)'
                      e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)'
                      e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'
                      e.currentTarget.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
                    }}
                  >
                    <div className="portal-icon-wrapper" style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: p.id === 'parent' ? 'rgba(59, 130, 246, 0.15)' : p.id === 'therapist' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                      color: p.id === 'parent' ? '#3b82f6' : p.id === 'therapist' ? '#10b981' : '#f59e0b',
                      fontSize: '1.5rem',
                      marginBottom: '1.25rem'
                    }}>
                      {p.id === 'parent' && '👥'}
                      {p.id === 'therapist' && '🩺'}
                      {p.id === 'admin' && '🛡️'}
                    </div>
                    <h3 className="portal-card-title" style={{ fontSize: '1.25rem', fontWeight: '700', margin: '0 0 0.5rem 0' }}>{p.label} Portal</h3>
                    <p className="portal-card-desc" style={{ fontSize: '0.875rem', color: 'var(--color-text-muted, #9ca3af)', margin: '0', lineHeight: '1.5' }}>{p.subtitle}</p>

                    <span className="portal-card-action" style={{
                      marginTop: 'auto',
                      paddingTop: '1.5rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      fontSize: '0.875rem',
                      fontWeight: '600',
                      color: 'var(--color-primary, #6366f1)'
                    }}>
                      Open portal <span style={{ transition: 'transform 0.2s' }}>→</span>
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
              <p className="login-brand">InsighteCase</p>
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
                  Finance, HR, and case managers all use the staff portal with role-based navigation.
                </p>
              ) : null}
            </aside>
          )}
        </section>
      </div>
    </div>
  )
}
