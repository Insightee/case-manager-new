import { useMemo, useState } from 'react'
import { Sidebar } from './components/layout/Sidebar.jsx'
import { MyCasesPage } from './components/cases/MyCasesPage.jsx'
import { DailyLogsPage } from './components/daily-logs/DailyLogsPage.jsx'
import { MonthlyReportsPage } from './components/monthly-reports/MonthlyReportsPage.jsx'
import { InvoicesPage } from './components/invoices/InvoicesPage.jsx'
import { ClientDashboardPage } from './components/client-portal/ClientDashboardPage.jsx'
import { ClientReportsPage } from './components/client-portal/ClientReportsPage.jsx'
import { ClientIEPAcknowledgementPage } from './components/client-portal/ClientIEPAcknowledgementPage.jsx'
import { ClientBillingPage } from './components/client-portal/ClientBillingPage.jsx'
import { ClientSupportPage } from './components/client-portal/ClientSupportPage.jsx'
import {
  getApprovedReports,
  getBillingSummaries,
  getIepStatus,
  getParentCases,
  recordParentAuditEvent,
} from './components/client-portal/clientPortalService.js'

const kpis = [
  { title: 'Total Cases', value: 42, meta: '+4 this month' },
  { title: 'Active Sessions', value: 18, meta: '7 ongoing now' },
  { title: 'Pending Logs', value: 3, meta: 'Need submission today' },
  { title: 'Log Compliance', value: '89%', meta: 'Target 95%' },
]

const sessions = [
  {
    time: '09:00 AM',
    child: 'Aarav M.',
    caseId: 'IC-2026-041',
    service: 'Shadow Support',
    status: 'Completed',
  },
  {
    time: '11:00 AM',
    child: 'Ira K.',
    caseId: 'IC-2026-053',
    service: 'Homecare',
    status: 'In Progress',
  },
  {
    time: '02:00 PM',
    child: 'Vihaan R.',
    caseId: 'IC-2026-067',
    service: 'Homecare',
    status: 'Upcoming',
  },
]

const pendingLogs = [
  { child: 'Ira K.', caseId: 'IC-2026-053', due: 'Today, 6:00 PM' },
  { child: 'Mira S.', caseId: 'IC-2026-028', due: 'Today, 8:00 PM' },
  { child: 'Rudra J.', caseId: 'IC-2026-035', due: 'Tomorrow, 10:00 AM' },
]

const topPerformers = [
  { name: 'Neha R.', score: '96%' },
  { name: 'Karan P.', score: '93%' },
  { name: 'Asha M.', score: '91%' },
  { name: 'Dev K.', score: '89%' },
  { name: 'Ishita S.', score: '87%' },
]

const notifications = [
  {
    title: 'Missing daily log reminder',
    time: '10 mins ago',
    detail: 'Case IC-2026-053 log not submitted for today.',
  },
  {
    title: 'Monthly report approved',
    time: '1 hour ago',
    detail: 'Case IC-2026-041 report approved by case manager.',
  },
  {
    title: 'Invoice status updated',
    time: 'Yesterday',
    detail: 'March invoice marked as paid by finance.',
  },
]

const parentNotifications = [
  {
    id: 'ntf-1',
    title: 'New report published',
    detail: 'Apr 2026 report for IC-2026-041 is now available.',
    createdAt: 'Today',
  },
  {
    id: 'ntf-2',
    title: 'IEP acknowledgement pending',
    detail: 'Please acknowledge IEP v2 for IC-2026-041.',
    createdAt: 'Yesterday',
  },
]

const settingGroups = [
  {
    title: 'Profile',
    items: ['Personal details', 'Availability slots', 'Specialization tags'],
  },
  {
    title: 'Notifications',
    items: ['Push reminders', 'Daily digest email', 'Escalation alerts'],
  },
  {
    title: 'Preferences',
    items: ['Language', 'Theme mode', 'Week start day'],
  },
]

const CLIENT_PORTAL_ENABLED = true
const DEFAULT_MOCK_USERS = {
  therapist: { username: 'therapist', password: 'demo123' },
  parent: { username: 'parent', password: 'demo123' },
}

function LoginPage({ onLogin, onSignup, clientPortalEnabled }) {
  const [mode, setMode] = useState('signin')
  const [role, setRole] = useState('therapist')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const isSignUp = mode === 'signup'

  function isValidEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
  }

  function handleSubmit(event) {
    event.preventDefault()

    if (role === 'parent' && !clientPortalEnabled) {
      setError('Client portal is currently disabled.')
      return
    }

    if (isSignUp) {
      if (!fullName.trim()) {
        setError('Full name is required.')
        return
      }
      if (!isValidEmail(email.trim())) {
        setError('Please enter a valid email.')
        return
      }
      if (password.trim().length < 6) {
        setError('Password must be at least 6 characters.')
        return
      }
      onSignup({
        role,
        username: email.trim().toLowerCase(),
        password,
      })
      setMode('signin')
      setError('')
      setPassword('')
      return
    }

    if (!isValidEmail(email.trim())) {
      setError('Please enter a valid email.')
      return
    }
    if (!password) {
      setError('Password is required.')
      return
    }

    const ok = onLogin({
      role,
      username: email.trim().toLowerCase(),
      password,
    })
    if (!ok) {
      setError('Invalid credentials for selected portal.')
      return
    }
    setError('')
  }

  return (
    <div className="login-shell">
      <div className="auth-bg-shapes" aria-hidden />
      <section className={`login-card login-card--split ${isSignUp ? 'is-signup' : 'is-signin'}`}>
        <div className="login-main">
          <p className="login-brand">InsightCase</p>
          <h1>{isSignUp ? 'Create your account' : 'Sign in to InsightCase'}</h1>
          <p className="login-sub">
            {isSignUp
              ? 'Register as therapist or client and start securely.'
              : 'Access therapist and client workflows securely.'}
          </p>

          <div className="login-socials">
            <button type="button">f</button>
            <button type="button">G+</button>
            <button type="button">in</button>
          </div>

          <div className={`auth-mode-toggle ${isSignUp ? 'is-signup' : 'is-signin'}`}>
            <span className="auth-mode-toggle__thumb" aria-hidden />
            <button type="button" onClick={() => setMode('signin')}>
              Sign In
            </button>
            <button type="button" onClick={() => setMode('signup')}>
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            {isSignUp ? (
              <label>
                Full Name
                <input
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  placeholder="Enter your full name"
                />
              </label>
            ) : null}

            <label>
              Portal Role
              <select value={role} onChange={(event) => setRole(event.target.value)}>
                <option value="therapist">Therapist Portal</option>
                <option value="parent">Client Portal</option>
              </select>
            </label>

            <label>
              Email
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder={role === 'parent' ? 'parent@demo.com' : 'therapist@demo.com'}
              />
            </label>

            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter password"
              />
            </label>

            {!isSignUp ? (
              <button type="button" className="login-link">
                Forgot your password?
              </button>
            ) : null}

            {error ? <p className="login-error">{error}</p> : null}

            <button type="submit" className="login-submit">
              {isSignUp ? 'Sign Up' : 'Sign In'}
            </button>
          </form>

          <p className="login-inline-toggle">
            {isSignUp ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button type="button" onClick={() => setMode(isSignUp ? 'signin' : 'signup')}>
              {isSignUp ? 'Sign in' : 'Sign up'}
            </button>
          </p>

          <div className="login-hint">
            <p>Demo accounts:</p>
            <p>
              <code>therapist@demo.com / demo123</code>
            </p>
            <p>
              <code>parent@demo.com / demo123</code>
            </p>
          </div>
        </div>

        <aside className={`login-side ${isSignUp ? 'is-signup' : 'is-signin'}`}>
          <h2>{isSignUp ? 'Welcome Back!' : 'Hello, Friend!'}</h2>
          <p>
            {isSignUp
              ? 'Already registered? Sign in and continue your journey.'
              : 'Enter your details and start your journey with InsightCase.'}
          </p>
          <button
            type="button"
            className={`login-side__toggle-btn ${isSignUp ? 'is-signup' : 'is-signin'}`}
            onClick={() => setMode(isSignUp ? 'signin' : 'signup')}
          >
            {isSignUp ? 'SIGN IN' : 'SIGN UP'}
          </button>
        </aside>
      </section>
    </div>
  )
}

function SectionHeader({ title, subtitle, actionLabel }) {
  return (
    <header className="topbar">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      <div className="topbar-actions">
        <input placeholder="Search child, case ID..." />
        <button type="button">{actionLabel}</button>
      </div>
    </header>
  )
}

function DashboardPage() {
  return (
    <>
      <SectionHeader
        title="Dashboard"
        subtitle="Good Morning, Neha. Let&apos;s manage your cases in one place."
        actionLabel="+ New Log"
      />

      <section className="kpi-grid">
        {kpis.map((item) => (
          <article key={item.title} className="card kpi-card">
            <p className="kpi-title">{item.title}</p>
            <p className="kpi-value">{item.value}</p>
            <p className="kpi-meta">{item.meta}</p>
          </article>
        ))}
      </section>

      <section className="panel-grid panel-grid-attendance">
        <article className="card attendance-card">
          <h3>Your Attendance</h3>
          <p className="attendance-timer">02:15:10</p>
          <div className="attendance-meta">
            <p>
              Break Time <span>01:00 PM - 01:45 PM</span>
            </p>
            <p>
              Target Hours <span>08:00 hrs/day</span>
            </p>
          </div>
          <div className="attendance-actions">
            <button type="button" className="secondary-btn">
              Break
            </button>
            <button type="button">Clock Out</button>
          </div>
        </article>

        <article className="card chart-card">
          <div className="card-head">
            <h3>Session Attendance Overview</h3>
            <button type="button">2026</button>
          </div>
          <div className="fake-chart">
            {[78, 52, 86, 69, 80, 74, 49, 84, 79, 61, 88, 93].map((v, i) => (
              <span key={`${v}-${i}`} style={{ height: `${v}%` }} />
            ))}
          </div>
          <div className="chart-legend">
            <p>
              <i className="legend-on-time" />
              On Time
            </p>
            <p>
              <i className="legend-late" />
              Late Log
            </p>
            <p>
              <i className="legend-missing" />
              Missing
            </p>
          </div>
        </article>
      </section>

      <section className="panel-grid">
        <article className="card">
          <div className="card-head">
            <h3>Today&apos;s Sessions</h3>
            <button type="button">View all</button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Child</th>
                  <th>Case ID</th>
                  <th>Service</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((item) => (
                  <tr key={`${item.caseId}-${item.time}`}>
                    <td>{item.time}</td>
                    <td>{item.child}</td>
                    <td>{item.caseId}</td>
                    <td>{item.service}</td>
                    <td>
                      <span
                        className={`status ${item.status.toLowerCase().replace(' ', '-')}`}
                      >
                        {item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="card">
          <div className="card-head">
            <h3>Pending Logs</h3>
            <button type="button">Set reminders</button>
          </div>
          <ul className="log-list">
            {pendingLogs.map((item) => (
              <li key={item.caseId}>
                <div>
                  <p>{item.child}</p>
                  <span>{item.caseId}</span>
                </div>
                <div>
                  <p>{item.due}</p>
                  <button type="button">Fill log</button>
                </div>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section className="panel-grid">
        <article className="card quick-actions">
          <h3>Quick Actions</h3>
          <div>
            <button type="button">Submit observation report</button>
            <button type="button">View monthly report draft</button>
            <button type="button">Generate invoice preview</button>
          </div>
        </article>

        <article className="card notice">
          <h3>Compliance Snapshot</h3>
          <p>3 missing logs need submission before day close.</p>
          <p>1 observation report due in 2 days.</p>
          <p>Finance marked 1 invoice as queried.</p>
        </article>
      </section>

      <section className="card performers">
        <div className="card-head">
          <h3>Top Performing Therapists</h3>
          <button type="button">View rankings</button>
        </div>
        <div className="performer-list">
          {topPerformers.map((item) => (
            <article key={item.name}>
              <span>{item.name.slice(0, 1)}</span>
              <p>{item.name}</p>
              <small>{item.score}</small>
            </article>
          ))}
        </div>
      </section>
    </>
  )
}

function CasesPage() {
  return <MyCasesPage />
}

function NotificationsPage() {
  return (
    <>
      <SectionHeader
        title="Notifications"
        subtitle="Stay updated on logs, reports, and invoice actions."
        actionLabel="Mark all read"
      />
      <section className="card">
        <div className="card-head">
          <h3>Recent Alerts</h3>
          <button type="button">Preferences</button>
        </div>
        <ul className="alerts-list">
          {notifications.map((item) => (
            <li key={item.title}>
              <div>
                <p>{item.title}</p>
                <span>{item.detail}</span>
              </div>
              <small>{item.time}</small>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}

function SettingsPage() {
  return (
    <>
      <SectionHeader
        title="Settings"
        subtitle="Manage your account, preferences, and notification options."
        actionLabel="Save changes"
      />
      <section className="panel-grid">
        {settingGroups.map((group) => (
          <article className="card settings-group" key={group.title}>
            <h3>{group.title}</h3>
            <ul>
              {group.items.map((item) => (
                <li key={item}>
                  <span>{item}</span>
                  <button type="button">Edit</button>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>
    </>
  )
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [mockUsers, setMockUsers] = useState({
    therapist: { ...DEFAULT_MOCK_USERS.therapist, username: 'therapist@demo.com' },
    parent: { ...DEFAULT_MOCK_USERS.parent, username: 'parent@demo.com' },
  })
  const [activeRole, setActiveRole] = useState('therapist')
  const [activePage, setActivePage] = useState('dashboard')
  const [currentParentId] = useState('parent-001')
  const [iepItems, setIepItems] = useState(() => getIepStatus('parent-001'))

  const parentCases = useMemo(() => getParentCases(currentParentId), [currentParentId])
  const parentReports = useMemo(() => getApprovedReports(currentParentId), [currentParentId])
  const billingItems = useMemo(() => getBillingSummaries(currentParentId), [currentParentId])

  function setPortalRole(nextRole) {
    if (nextRole === 'parent' && !CLIENT_PORTAL_ENABLED) {
      return
    }

    setActiveRole(nextRole)
    setActivePage(nextRole === 'parent' ? 'client-dashboard' : 'dashboard')
  }

  function handleLogin({ role, username, password }) {
    const expected = mockUsers[role]
    if (!expected || expected.username !== username || expected.password !== password) {
      return false
    }
    setIsAuthenticated(true)
    setPortalRole(role)
    return true
  }

  function handleSignup(payload) {
    setMockUsers((prev) => ({
      ...prev,
      [payload.role]: {
        username: payload.username,
        password: payload.password,
      },
    }))
  }

  function handleLogout() {
    setIsAuthenticated(false)
    setActiveRole('therapist')
    setActivePage('dashboard')
  }

  function handleParentReportView(report) {
    recordParentAuditEvent('report_viewed', {
      reportId: report.id,
      caseId: report.caseId,
    })
    window.alert(`Opened approved report: ${report.childName} (${report.month})`)
  }

  function handleIepAcknowledge(iepId) {
    setIepItems((prev) =>
      prev.map((item) =>
        item.id === iepId
          ? {
              ...item,
              status: 'acknowledged',
              acknowledgedAt: new Date().toISOString(),
            }
          : item,
      ),
    )
    recordParentAuditEvent('iep_acknowledged', { iepId })
  }

  function handleSupportSubmit(payload) {
    recordParentAuditEvent('support_requested', payload)
  }

  const currentPage = useMemo(() => {
    if (activeRole === 'parent') {
      switch (activePage) {
        case 'client-reports':
          return <ClientReportsPage reports={parentReports} onViewReport={handleParentReportView} />
        case 'client-iep':
          return <ClientIEPAcknowledgementPage iepItems={iepItems} onAcknowledge={handleIepAcknowledge} />
        case 'client-billing':
          return <ClientBillingPage billingItems={billingItems} />
        case 'client-support':
          return <ClientSupportPage onSubmit={handleSupportSubmit} />
        default:
          return (
            <ClientDashboardPage
              cases={parentCases}
              reports={parentReports}
              iepItems={iepItems}
              notifications={parentNotifications}
            />
          )
      }
    }

    switch (activePage) {
      case 'cases':
        return <CasesPage />
      case 'logs':
        return <DailyLogsPage />
      case 'reports':
        return <MonthlyReportsPage />
      case 'invoices':
        return <InvoicesPage />
      case 'notifications':
        return <NotificationsPage />
      case 'settings':
        return <SettingsPage />
      default:
        return <DashboardPage />
    }
  }, [activePage, activeRole, billingItems, iepItems, parentCases, parentReports])

  if (!isAuthenticated) {
    return (
      <LoginPage
        onLogin={handleLogin}
        onSignup={handleSignup}
        clientPortalEnabled={CLIENT_PORTAL_ENABLED}
      />
    )
  }

  return (
    <div className="app-shell">
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        role={activeRole}
        onLogout={handleLogout}
      />

      <main className="content">{currentPage}</main>
    </div>
  )
}

export default App
