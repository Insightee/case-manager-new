import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

const PORTALS = [
  {
    id: 'therapist',
    label: 'Therapist',
    subtitle: 'Daily logs, cases, reports, and invoices.',
    placeholder: 'therapist@demo.com',
    demos: [{ email: 'therapist@demo.com', label: 'Therapist' }],
  },
  {
    id: 'parent',
    label: 'Client',
    subtitle: 'Approved reports, IEP acknowledgements, and billing.',
    placeholder: 'parent@demo.com',
    demos: [{ email: 'parent@demo.com', label: 'Parent / Guardian' }],
  },
  {
    id: 'admin',
    label: 'Admin',
    subtitle: 'Cases, reviews, assignments, and operations.',
    placeholder: 'superadmin@demo.com',
    demos: [
      { email: 'superadmin@demo.com', label: 'Super Admin' },
      { email: 'casemanager@demo.com', label: 'Case Manager' },
      { email: 'finance@demo.com', label: 'Finance' },
      { email: 'admin@demo.com', label: 'Module admin' },
      { email: 'viewer@demo.com', label: 'View only' },
      { email: 'supervisor@demo.com', label: 'Supervisor' },
      { email: 'casemanager@demo.com', label: 'Case manager' },
    ],
  },
]

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [portal, setPortal] = useState('therapist')
  const [email, setEmail] = useState('therapist@demo.com')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const active = useMemo(() => PORTALS.find((p) => p.id === portal) ?? PORTALS[0], [portal])

  function selectPortal(id) {
    setPortal(id)
    setError('')
    const next = PORTALS.find((p) => p.id === id)
    if (next?.demos[0]) setEmail(next.demos[0].email)
  }

  function fillDemo(demoEmail) {
    setEmail(demoEmail)
    setPassword('demo123')
    setError('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      await login(email.trim().toLowerCase(), password)
      navigate('/')
    } catch (err) {
      setError(err.message || 'Invalid credentials.')
    }
  }

  return (
    <div className="login-page">
      <div className="login-shell">
        <section className="login-card">
          <div className="login-main">
            <header className="login-header">
              <p className="login-brand">InsightCase</p>
              <h1 className="login-title">{active.label} portal</h1>
              <p className="login-sub">{active.subtitle}</p>
            </header>

            <div className="portal-tabs" role="tablist" aria-label="Select portal">
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
              {error ? (
                <p className="login-error" role="alert">
                  {error}
                </p>
              ) : null}
              <button type="submit" className="login-submit">
                Sign in
              </button>
            </form>

            <div className="login-hint">
              <p className="login-hint__label">
                Demo · password <code>demo123</code>
              </p>
              <ul className="login-demo-list">
                {active.demos.map((d) => (
                  <li key={d.email}>
                    <button type="button" className="login-demo-btn" onClick={() => fillDemo(d.email)}>
                      <span className="login-demo-btn__role">{d.label}</span>
                      <code>{d.email}</code>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <aside className="login-aside" aria-hidden="true">
            <p className="login-aside__tag">Case-centric care</p>
            <h2>One platform for your whole team</h2>
            <ul className="login-aside__list">
              <li className={portal === 'therapist' ? 'is-active' : ''}>Therapist</li>
              <li className={portal === 'parent' ? 'is-active' : ''}>Client</li>
              <li className={portal === 'admin' ? 'is-active' : ''}>Admin</li>
            </ul>
          </aside>
        </section>
      </div>
    </div>
  )
}
