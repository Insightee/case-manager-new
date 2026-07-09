import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/apiClient.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useTherapistFrequentActions } from '../hooks/useTherapistFrequentActions.js'
import { useTherapistHome, useTherapistReportsPipeline } from '../hooks/useTherapistHome.js'
import { QueryState } from '../components/shared/QueryState.jsx'
import { TherapistDashboardIcon } from '../components/therapist/TherapistDashboardIcon.jsx'
import { formatDisplayDate, formatDisplayDateTime } from '../lib/datetime.js'
import { isToday } from '../lib/therapistSchedule.js'
import { isBillingModuleEnabled, isReportsModuleEnabled } from '../lib/productFeatureFlags.js'
import '../styles/therapist-dashboard.css'

function dateBlockParts(iso) {
  const d = iso ? new Date(`${iso}T00:00:00`) : null
  if (!d || Number.isNaN(d.getTime())) return { month: '—', day: '—' }
  return {
    month: d.toLocaleString('en-US', { month: 'short' }).toUpperCase(),
    day: String(d.getDate()),
  }
}

function durationMinutes(start, end) {
  if (!start || !end) return null
  const [sh, sm] = start.split(':').map(Number)
  const [eh, em] = end.split(':').map(Number)
  if ([sh, sm, eh, em].some((n) => Number.isNaN(n))) return null
  const mins = eh * 60 + em - (sh * 60 + sm)
  return mins > 0 ? mins : null
}

function scheduleTag(item) {
  if (item.subtitle) return item.subtitle
  if (item.kind === 'booking') {
    return item.bookingSource === 'PARENT' ? 'Parent booking' : 'Calendar'
  }
  return 'Session'
}

export function TherapistDashboardPage() {
  const { user } = useAuth()
  const { data: home, isLoading, isError, error, refetch } = useTherapistHome()
  const { data: reportsPipeline } = useTherapistReportsPipeline()
  const { actions, trackClick } = useTherapistFrequentActions(4)

  const greeting = (() => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  })()

  const stats = home?.stats
  const active = home?.active_session
  const needsLog = home?.needs_log_sessions || []
  const schedule = home?.schedule_preview || []
  const todayItems = schedule.filter((s) => isToday(s.date))
  const scheduleList = (todayItems.length > 0 ? todayItems : schedule).slice(0, 6)
  const scheduleTitle = todayItems.length > 0 ? 'Today’s Schedule' : 'Upcoming Schedule'
  const criticalCases = (home?.cases_board?.allCases || []).filter((c) => c.critical).slice(0, 3)
  const pendingAssignments = home?.pending_assignment_acceptance || []
  const pendingCmMeetings = home?.pending_cm_meetings || []
  const urgentMeeting = pendingCmMeetings[0] || null
  const reportsDue = isReportsModuleEnabled() ? (reportsPipeline?.attention || []).slice(0, 3) : []
  const billingOn = isBillingModuleEnabled()
  const reportsOn = isReportsModuleEnabled()

  const attentionItems = [
    ...needsLog.slice(0, 3).map((s) => ({
      key: `log-${s.id}`,
      to: `/therapist/logs?session=${s.id}`,
      title: s.child_name || s.case_code || 'Client',
      meta: s.scheduled_date ? `Visit · ${formatDisplayDate(s.scheduled_date)}` : 'Completed visit',
      badge: 'Log due',
      tone: 'danger',
    })),
    ...criticalCases.map((c) => ({
      key: `case-${c.id}`,
      to: `/therapist/cases/${c.id}`,
      title: c.child,
      meta: c.nextDue,
      badge: 'Attention',
      tone: 'warn',
    })),
  ].slice(0, 5)

  const [acceptBusy, setAcceptBusy] = useState(null)
  const [acceptErr, setAcceptErr] = useState('')

  return (
    <div className="therapist-dashboard-page forest-light">
      {/* Header */}
      <header className="td-header">
        <div className="td-header__intro">
          <h2 className="td-header__title">
            {greeting}, {user?.full_name?.split(' ')[0] || 'there'}
          </h2>
          <p className="td-header__status">
            <span className="td-header__status-dot" aria-hidden="true" />
            {todayItems.length > 0
              ? `${todayItems.length} visit${todayItems.length === 1 ? '' : 's'} today`
              : 'No visits scheduled today'}
            {stats?.needs_log ? ` · ${stats.needs_log} log${stats.needs_log === 1 ? '' : 's'} due` : ''}
          </p>
        </div>
        <div className="td-header__chips">
          <Link to="/therapist/logs#upcoming" className="td-chip">
            <TherapistDashboardIcon name="calendar_month" tone="forest" />
            <span className="td-chip__body">
              <span className="td-chip__eyebrow">Upcoming</span>
              <span className="td-chip__value">
                {schedule.length} Session{schedule.length === 1 ? '' : 's'}
              </span>
            </span>
          </Link>
          <Link to="/therapist/logs" className="td-chip">
            <TherapistDashboardIcon name="edit_note" tone="amber" />
            <span className="td-chip__body">
              <span className="td-chip__eyebrow">Tasks</span>
              <span className="td-chip__value">{stats?.needs_log ?? 0} Logs Due</span>
            </span>
          </Link>
        </div>
      </header>

      <QueryState isLoading={isLoading} isError={isError} error={error} onRetry={() => refetch()}>
        {/* Urgent banner */}
        {urgentMeeting ? (
          <Link
            to={urgentMeeting.case_id ? `/therapist/meetings?case_id=${urgentMeeting.case_id}` : '/therapist/meetings'}
            className="td-urgent"
          >
            <span className="td-urgent__icon" aria-hidden="true">
              <span className="material-symbols-outlined">priority_high</span>
            </span>
            <span className="td-urgent__body">
              <span className="td-urgent__head">
                <span className="td-urgent__tag">Urgent</span>
                <strong className="td-urgent__title">Submit meeting notes</strong>
              </span>
              <span className="td-urgent__meta">
                {[
                  urgentMeeting.child_name || urgentMeeting.case_code || urgentMeeting.title,
                  formatDisplayDateTime(urgentMeeting.scheduled_date, urgentMeeting.scheduled_time),
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </span>
            <span className="td-urgent__cta">Review Now</span>
          </Link>
        ) : active ? (
          <Link to="/therapist/logs" className="td-urgent td-urgent--active">
            <span className="td-urgent__icon" aria-hidden="true">
              <span className="material-symbols-outlined">play_circle</span>
            </span>
            <span className="td-urgent__body">
              <span className="td-urgent__head">
                <span className="td-urgent__tag td-urgent__tag--live">Live</span>
                <strong className="td-urgent__title">Session in progress</strong>
              </span>
              <span className="td-urgent__meta">Open logs to record evidence and close the visit.</span>
            </span>
            <span className="td-urgent__cta">Open Logs</span>
          </Link>
        ) : null}

        {/* New case assignments */}
        {pendingAssignments.length > 0 ? (
          <section className="td-card td-assignments">
            <h3 className="td-card__title">New case assignment</h3>
            <p className="td-card__hint">
              You can start sessions and logs for this case now. Marking reviewed is optional.
            </p>
            {acceptErr ? <p className="td-assignments__error">{acceptErr}</p> : null}
            <ul className="td-assignments__list">
              {pendingAssignments.map((item) => (
                <li key={item.assignment_id}>
                  <span>
                    <strong>{item.child_name}</strong> · {item.case_code}
                    {!item.parent_accepted ? (
                      <span className="td-assignments__wait">Waiting for parent</span>
                    ) : null}
                  </span>
                  <button
                    type="button"
                    className="td-btn td-btn--primary"
                    disabled={acceptBusy === item.assignment_id}
                    onClick={async () => {
                      setAcceptBusy(item.assignment_id)
                      setAcceptErr('')
                      try {
                        await apiFetch(`/api/v1/assignments/${item.assignment_id}/accept`, { method: 'POST' })
                        refetch()
                      } catch (e) {
                        setAcceptErr(e.message || 'Could not accept')
                      } finally {
                        setAcceptBusy(null)
                      }
                    }}
                  >
                    {acceptBusy === item.assignment_id ? 'Saving…' : 'Mark as reviewed'}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {/* Two-column body */}
        <div className="td-columns">
          <div className="td-main">
            <section className="td-card td-schedule" aria-labelledby="td-schedule-title">
              <div className="td-card__head">
                <h3 id="td-schedule-title" className="td-card__title">{scheduleTitle}</h3>
                <Link to="/therapist/slots" className="td-card__action">View Calendar</Link>
              </div>
              {scheduleList.length === 0 ? (
                <p className="td-empty">No upcoming visits. Book slots from Scheduling.</p>
              ) : (
                <ul className="td-schedule__list">
                  {scheduleList.map((item) => {
                    const { month, day } = dateBlockParts(item.date)
                    const mins = durationMinutes(item.startTime, item.endTime)
                    const href = item.sessionId
                      ? `/therapist/logs?session=${item.sessionId}`
                      : item.caseId
                        ? `/therapist/cases/${item.caseId}`
                        : '/therapist/logs'
                    return (
                      <li key={item.key}>
                        <Link to={href} className="td-schedule__row">
                          <span
                            className={`td-schedule__date${isToday(item.date) ? ' td-schedule__date--today' : ''}`}
                            aria-hidden="true"
                          >
                            <span className="td-schedule__date-month">{month}</span>
                            <span className="td-schedule__date-day">{day}</span>
                          </span>
                          <span className="td-schedule__info">
                            <strong className="td-schedule__name">{item.childName || item.caseCode}</strong>
                            <span className="td-schedule__when">
                              <span className="material-symbols-outlined" aria-hidden="true">schedule</span>
                              {item.startTime} – {item.endTime}
                              {mins ? ` (${mins} min)` : ''}
                            </span>
                          </span>
                          <span className="td-schedule__tag">{scheduleTag(item)}</span>
                        </Link>
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>
          </div>

          <div className="td-side">
            {/* Attention Needed */}
            <section className="td-card" aria-labelledby="td-attention-title">
              <div className="td-card__head">
                <h3 id="td-attention-title" className="td-card__title">Attention Needed</h3>
              </div>
              {attentionItems.length === 0 ? (
                <p className="td-empty">All caught up — nothing needs you right now.</p>
              ) : (
                <ul className="td-attention__list">
                  {attentionItems.map((item) => (
                    <li key={item.key}>
                      <Link to={item.to} className="td-attention__row">
                        <span className="td-attention__info">
                          <strong className="td-attention__name">{item.title}</strong>
                          <span className="td-attention__meta">{item.meta}</span>
                        </span>
                        <span className={`td-badge td-badge--${item.tone}`}>{item.badge}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              <Link to="/therapist/logs" className="td-card__footer-link">Manage All Tasks</Link>
            </section>

            {/* Reports Due */}
            {reportsOn ? (
            <section className="td-card" aria-labelledby="td-reports-title">
              <div className="td-card__head">
                <h3 id="td-reports-title" className="td-card__title">Reports Due</h3>
              </div>
              {reportsDue.length === 0 ? (
                <p className="td-empty">No reports waiting on you.</p>
              ) : (
                <ul className="td-reports__list">
                  {reportsDue.map((r) => (
                    <li key={r.id}>
                      <Link
                        to={r.caseDbId ? `/therapist/cases/${r.caseDbId}?tab=reports&section=monthly` : '/therapist/reports'}
                        className="td-reports__row"
                      >
                        <span className="td-reports__info">
                          <strong className="td-reports__name">{r.month || 'Monthly Report'}</strong>
                          <span className="td-reports__meta">
                            {[r.child, r.dueInfo || r.statusLabel].filter(Boolean).join(' · ')}
                          </span>
                        </span>
                        <span className="material-symbols-outlined td-reports__icon" aria-hidden="true">
                          description
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              <Link to="/therapist/reports" className="td-card__footer-link">Open Reports</Link>
            </section>
            ) : null}

            {/* Billing Due — module gated */}
            {billingOn ? (
              <section className="td-card" aria-labelledby="td-billing-title">
                <div className="td-card__head">
                  <h3 id="td-billing-title" className="td-card__title">Billing</h3>
                </div>
                <p className="td-empty">Review sessions and submit your invoice.</p>
                <Link to="/therapist/invoices" className="td-card__footer-link">Process All Billing</Link>
              </section>
            ) : null}

            {/* Quick Shortcuts */}
            <section className="td-shortcuts" aria-labelledby="td-shortcuts-title">
              <h3 id="td-shortcuts-title" className="td-shortcuts__title">Quick Shortcuts</h3>
              <ul className="td-shortcuts__grid">
                {actions.slice(0, 4).map((action) => (
                  <li key={action.id}>
                    <Link
                      to={action.to}
                      className="td-shortcuts__tile"
                      onClick={() => trackClick(action.id)}
                    >
                      <TherapistDashboardIcon name={action.icon} tone="forest" />
                      <span className="td-shortcuts__label">{action.label}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>

            {/* Caseload summary (dark card) */}
            <Link to="/therapist/cases" className="td-growth">
              <span className="td-growth__body">
                <strong className="td-growth__title">My Caseload</strong>
                <span className="td-growth__meta">
                  {stats?.case_count ?? 0} active case{(stats?.case_count ?? 0) === 1 ? '' : 's'}
                  {stats?.draft_reports ? ` · ${stats.draft_reports} report draft${stats.draft_reports === 1 ? '' : 's'}` : ''}
                </span>
              </span>
              <span className="td-growth__bars" aria-hidden="true">
                <i /><i /><i /><i /><i />
              </span>
            </Link>
          </div>
        </div>
      </QueryState>
    </div>
  )
}
