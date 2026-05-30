import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { SkipLink } from '../components/shared/SkipLink.jsx'
import { usePageMeta } from '../hooks/usePageMeta.js'

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
    subtitle: 'Case managers, module admins, finance, and HR — password demo123 for all.',
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
  const msg = err?.message || 'Sign-in failed.'
  if (/invalid credentials/i.test(msg)) {
    const hostname = typeof window !== 'undefined' ? window.location.hostname : ''
    const localDev = hostname === 'localhost' || hostname === '127.0.0.1'
    if (localDev) {
      return `${msg} For local dev, run: cd backend && python3 -m app.seed.demo_seed (resets demo123 passwords).`
    }
    return `${msg} Demo accounts use password demo123 — pick one from the list below (Staff tab for admin). Invited personal emails must open the invite link and set a password first; demo123 does not apply to those accounts.`
  }
  if (/timed out/i.test(msg)) {
    const hostname = typeof window !== 'undefined' ? window.location.hostname : ''
    const localDev = hostname === 'localhost' || hostname === '127.0.0.1'
    if (localDev) {
      return `${msg} Ensure uvicorn is running on port 8000, or use an empty VITE_API_URL with npm run dev.`
    }
    return `${msg} The API may be unreachable — check your connection or contact your administrator.`
  }
  return msg
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [portal, setPortal] = useState('therapist')
  const [email, setEmail] = useState('therapist@demo.com')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [selectedDemoEmail, setSelectedDemoEmail] = useState('')

  const active = useMemo(() => PORTALS.find((p) => p.id === portal) ?? PORTALS[0], [portal])
  const activeDemos = useMemo(() => flattenDemos(active), [active])

  usePageMeta({
    title: 'Sign in',
    description: `Sign in to the InsightCase ${active.label.toLowerCase()} portal.`,
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
      await login(demoEmail.trim().toLowerCase(), DEMO_PASSWORD)
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
      await login(email.trim().toLowerCase(), password)
      navigate('/')
    } catch (err) {
      setError(formatLoginError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const isStaffPortal = portal === 'admin'

  function demoButtonClass(demoEmail) {
    return `login-demo-btn${selectedDemoEmail === demoEmail ? ' is-selected' : ''}`
  }

  return (
    <div className="login-page">
      <SkipLink />
      <div className="login-shell">
        <section className="login-card">
          <main id="main-content" className="login-main" tabIndex={-1}>
            <header className="login-header">
              <p className="login-brand">InsightCase</p>
              <h1 className="login-title">{active.label} portal</h1>
              <p className="login-sub">{active.subtitle}</p>
            </header>

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

            <form onSubmit={handleSubmit} className="login-form">
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={active.placeholder}
                  autoComplete="username"
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
              </label>
              <p className="login-sub" style={{ marginTop: '-0.5rem', textAlign: 'right' }}>
                <Link to="/forgot-password">Forgot password?</Link>
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
          </main>

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
        </section>
      </div>
    </div>
  )
}
