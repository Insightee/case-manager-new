import { Link } from 'react-router-dom'
import { AdminPanel, AdminStatCard, formatCurrency } from './ui/index.js'

function money(mod, key) {
  if (!mod || mod.ok === false || mod.unavailable) return 'Unavailable'
  const value = mod[key]
  if (value == null) return 'Unavailable'
  return formatCurrency(value)
}

function ModuleError({ mod }) {
  if (!mod || (mod.ok && !mod.unavailable)) return null
  if (mod.unavailable && mod.reason) {
    return <p className="admin-muted">{mod.reason}</p>
  }
  if (mod.ok === false) {
    return <p className="admin-alert admin-alert--error">{mod.error || 'This module could not load.'}</p>
  }
  return null
}

const STATUS_ORDER = [
  ['PENDING_ALLOTMENT', 'Pending allotment'],
  ['ACTIVE', 'Active'],
  ['PENDING_REPLACEMENT', 'Pending replacement'],
  ['SUSPENDED', 'Suspended'],
  ['DEACTIVATED', 'Deactivated'],
  ['CLOSED', 'Closed'],
]

const DIRECTORY = [
  { href: '/admin/cases', label: 'Cases', group: 'Business and cases' },
  { href: '/admin/workbench', label: 'Workbench queues', group: 'Work and approvals' },
  { href: '/admin/reports', label: 'Clinical review', group: 'Work and approvals' },
  { href: '/admin/therapist-attention', label: 'Therapist attention', group: 'Therapists and profiles' },
  { href: '/admin/therapist-profiles', label: 'Therapist profiles', group: 'Therapists and profiles' },
  { href: '/admin/attendance', label: 'Staff attendance', group: 'Attendance and delivery' },
  { href: '/admin/hr-reports', label: 'HR reports', group: 'Attendance and delivery' },
  { href: '/admin/logs', label: 'Session logs', group: 'Attendance and delivery' },
  { href: '/admin/finance-reports', label: 'Therapist payout preview', group: 'Finance' },
  { href: '/admin/invoices', label: 'Client invoices', group: 'Finance' },
  { href: '/admin/support?tab=ticket-report', label: 'Ticket report', group: 'Work and approvals' },
  { href: '/admin/data-exceptions', label: 'Data exceptions', group: 'Data quality' },
]

export function AdminLeadershipOverview({ leadership, operations }) {
  if (!leadership) return null
  const period = leadership.period || {}
  const modules = leadership.modules || {}
  const cases = modules.cases
  const assignments = modules.assignments
  const sessions = modules.sessions
  const finance = modules.finance
  const tickets = modules.tickets
  const attendance = modules.staffAttendance
  const queues = modules.queues
  const attention = modules.therapistAttention
  const exceptions = modules.dataExceptions
  const asOf = period.asOf ? `As of ${period.asOf}` : 'As of today'

  return (
    <div className="admin-leadership">
      <p className="admin-muted admin-leadership__refresh">
        Period {period.dateFrom} – {period.dateTo} ({period.timezone || 'Asia/Kolkata'}). Last refresh{' '}
        {period.generatedAt ? new Date(period.generatedAt).toLocaleString('en-IN') : '—'}.
      </p>

      <AdminPanel title="Case mix" subtitle="Current snapshot — every case status">
        <ModuleError mod={cases} />
        {cases?.ok && !cases.unavailable ? (
          <div className="admin-kpi-grid admin-leadership__grid">
            {STATUS_ORDER.map(([key, label]) => (
              <AdminStatCard
                key={key}
                title={label}
                value={cases.statusCounts?.[key] ?? 0}
                basis="Current"
                tone={key === 'ACTIVE' ? 'teal' : key === 'PENDING_ALLOTMENT' || key === 'PENDING_REPLACEMENT' ? 'amber' : 'slate'}
                to={`/admin/cases?status=${key}`}
              />
            ))}
          </div>
        ) : null}
      </AdminPanel>

      <AdminPanel
        title="Movement during period"
        subtitle={
          cases?.movementCoverage === 'partial'
            ? 'From case status audit — coverage is partial, so this is not an opening/closing caseload'
            : 'From case status audit. Created is not first activation.'
        }
      >
        <ModuleError mod={cases} />
        {cases?.ok && !cases.unavailable ? (
          <div className="admin-kpi-grid admin-leadership__grid">
            <AdminStatCard title="New cases created" value={cases.createdDuringPeriod} basis="During selected period" to="/admin/cases" />
            <AdminStatCard
              title="First activation"
              value={cases.firstActivationDuringPeriod}
              hint="First audit row to Active in range"
              basis="During selected period"
              to="/admin/cases?status=ACTIVE"
            />
            <AdminStatCard title="Reactivation" value={cases.reactivationDuringPeriod} basis="During selected period" />
            <AdminStatCard title="Suspension" value={cases.suspensionDuringPeriod} basis="During selected period" to="/admin/cases?status=SUSPENDED" />
            <AdminStatCard title="Closure" value={cases.closureDuringPeriod} basis="During selected period" to="/admin/cases?status=CLOSED" />
            <AdminStatCard title="Deactivation" value={cases.deactivationDuringPeriod} basis="During selected period" to="/admin/cases?status=DEACTIVATED" />
          </div>
        ) : null}
      </AdminPanel>

      <AdminPanel title="Assignment gaps" subtitle="Current therapist assignment — replacement is not first allotment">
        <ModuleError mod={assignments} />
        {assignments?.ok && !assignments.unavailable ? (
          <div className="admin-kpi-grid admin-leadership__grid">
            <AdminStatCard
              title="Awaiting first assignment"
              value={assignments.awaitingFirstAssignment}
              basis="Current"
              tone="amber"
              to={assignments.hrefFirst}
            />
            <AdminStatCard
              title="Awaiting replacement"
              value={assignments.awaitingReplacement}
              hint="Current therapist may still be delivering"
              basis="Current"
              tone="amber"
              to={assignments.hrefReplacement}
            />
            <AdminStatCard
              title="Active without assignment"
              value={assignments.activeWithoutActiveAssignment}
              basis="Current"
              tone="rose"
              to="/admin/data-exceptions"
            />
            <AdminStatCard
              title="Assignment ended events"
              value={assignments.assignmentEndedEvents}
              hint={`${assignments.uniqueCasesWithEndedAssignment ?? 0} unique cases. ${assignments.endedNote || ''}`}
              basis="During selected period"
            />
          </div>
        ) : null}
      </AdminPanel>

      <AdminPanel title="Sessions" subtitle={sessions?.autoClosedNote}>
        <ModuleError mod={sessions} />
        {sessions?.ok && !sessions.unavailable ? (
          <div className="admin-kpi-grid admin-leadership__grid">
            <AdminStatCard title="Completed" value={sessions.completed} basis="During selected period" to="/admin/logs" />
            <AdminStatCard title="Client absent" value={sessions.clientAbsent} basis="During selected period" />
            <AdminStatCard title="Therapist leave" value={sessions.therapistLeave} basis="During selected period" />
            <AdminStatCard title="Cancelled" value={sessions.cancelled} basis="During selected period" />
            <AdminStatCard title="No-show" value={sessions.noShow} basis="During selected period" />
            <AdminStatCard
              title="Auto-closed"
              value={sessions.autoClosed}
              hint="Not proof of attended delivery"
              basis="During selected period"
            />
          </div>
        ) : null}
      </AdminPanel>

      {finance ? (
        <AdminPanel title="Finance snapshot" subtitle="Invoiced amount and confirmed cash — not recognised revenue or net profit">
          <ModuleError mod={finance} />
          {finance.ok && !finance.unavailable ? (
            <div className="admin-kpi-grid admin-leadership__grid">
              <AdminStatCard
                title="Invoiced amount"
                value={money(finance, 'invoicedAmountInr')}
                basis="Billing month"
                to={finance.hrefInvoices}
                tone="rose"
              />
              <AdminStatCard
                title="Confirmed cash received"
                value={money(finance, 'confirmedCashInr')}
                hint={`${finance.pendingClaims ?? 0} pending claims (not in cash)`}
                basis="During selected period"
                to="/admin/invoices?tab=payments"
                tone="rose"
              />
              <AdminStatCard
                title="Current outstanding"
                value={money(finance, 'outstandingAmountInr')}
                hint={`${finance.outstandingCount ?? 0} open invoices`}
                basis={asOf}
                to={finance.hrefInvoices}
              />
              <AdminStatCard
                title="Current overdue"
                value={money(finance, 'overdueAmountInr')}
                hint={finance.overdueNote}
                basis={asOf}
              />
              <AdminStatCard
                title="Therapist statements in review"
                value={finance.therapistStatementsInReview}
                basis="Current"
                to={finance.hrefPayouts}
              />
              <AdminStatCard
                title="Approved awaiting payment"
                value={finance.approvedAwaitingPayment}
                hint="Not paid during the period"
                basis="Current"
                to={finance.hrefPayouts}
              />
            </div>
          ) : null}
        </AdminPanel>
      ) : null}

      <AdminPanel title="Support tickets" subtitle="Open and in progress are separate. Needs action is both.">
        <ModuleError mod={tickets} />
        {tickets?.ok && !tickets.unavailable ? (
          <div className="admin-kpi-grid admin-leadership__grid">
            <AdminStatCard title="Open" value={tickets.open} basis="Current" to={tickets.hrefOpen} />
            <AdminStatCard title="In progress" value={tickets.inProgress} basis="Current" to={tickets.hrefInProgress} />
            <AdminStatCard title="Needs action" value={tickets.needsAction} basis="Current" to={tickets.href} />
            <AdminStatCard title="Opened during period" value={tickets.openedDuringPeriod} basis="During selected period" to={tickets.href} />
          </div>
        ) : null}
      </AdminPanel>

      <AdminPanel title="Staff workplace attendance" subtitle={attendance?.sourceLabel || 'In-app clock-in'}>
        <ModuleError mod={attendance} />
        {attendance?.ok && !attendance.unavailable ? (
          <div className="admin-kpi-grid admin-leadership__grid">
            <AdminStatCard
              title="Clocked in today"
              value={attendance.clockedInToday}
              hint={`${attendance.todayGaps ?? 0} coverage gaps today`}
              basis="Current"
              to="/admin/attendance"
              tone="teal"
            />
            <AdminStatCard
              title="Staff with a record this period"
              value={attendance.uniqueStaffDuringPeriod}
              hint={`${attendance.recordsDuringPeriod ?? 0} clock-in records`}
              basis="During selected period"
              to="/admin/attendance"
            />
            <AdminStatCard
              title="Auto-closed this period"
              value={attendance.autoClosedDuringPeriod}
              basis="During selected period"
              to="/admin/attendance"
            />
            <AdminStatCard
              title="Coverage (ever clocked in)"
              value={attendance.coverageStaff}
              hint={attendance.coverageNote}
              basis={asOf}
              to="/admin/attendance"
            />
          </div>
        ) : null}
      </AdminPanel>

      <div className="admin-layout">
        <AdminPanel title="Therapist attention" subtitle={attention?.loginNote}>
          <ModuleError mod={attention} />
          {attention?.ok && !attention.unavailable ? (
            <div className="admin-kpi-grid admin-leadership__grid">
              <AdminStatCard title="Therapists" value={attention.therapistCount} basis="Current" to={attention.href} />
              <AdminStatCard
                title="No recorded login"
                value={attention.noRecordedLogin}
                hint="Not the same as never used"
                basis="Current"
                to={attention.href}
                tone="amber"
              />
              <AdminStatCard title="Pending profiles" value={attention.pendingProfiles} basis="Current" to="/admin/therapist-profiles" />
              <AdminStatCard
                title="Inactive with assignment"
                value={attention.inactiveWithActiveAssignment}
                basis="Current"
                to={attention.href}
                tone="rose"
              />
            </div>
          ) : null}
        </AdminPanel>
        <AdminPanel title="Data exceptions" subtitle="Live checks at generation time — not a stored history">
          <ModuleError mod={exceptions} />
          {exceptions?.ok && !exceptions.unavailable ? (
            <div className="admin-kpi-grid admin-leadership__grid">
              <AdminStatCard
                title="Confirmed"
                value={exceptions.confirmed}
                basis={asOf}
                to={exceptions.href}
                tone="rose"
              />
              <AdminStatCard
                title="Suspected"
                value={exceptions.suspected}
                hint="Multiple assignments or invoices are not automatic errors"
                basis={asOf}
                to={exceptions.href}
              />
            </div>
          ) : null}
        </AdminPanel>
      </div>

      <AdminPanel title="Work queues" subtitle={queues?.note}>
        <ModuleError mod={queues} />
        {queues?.ok && !queues.unavailable && queues.items?.length ? (
          <ul className="admin-leadership-queues">
            {queues.items.map((q) => (
              <li key={q.key}>
                <Link to={q.href} className="admin-leadership-queues__item">
                  <span>
                    <strong>{q.label}</strong>
                    <span className="admin-muted">
                      {' '}
                      · {q.owner} · {q.dateBasis === 'current' ? 'Current' : q.dateBasis}
                      {q.oldestAgeDays != null ? ` · oldest ${q.oldestAgeDays}d (${q.ageField})` : ''}
                      {q.overdueAvailable ? ` · ${q.overdue} overdue` : ''}
                    </span>
                  </span>
                  <span className="admin-leadership-queues__count">{q.count}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : queues?.ok && !queues.unavailable ? (
          <p className="admin-muted">No authorised queues for this account.</p>
        ) : null}
      </AdminPanel>

      {operations ? (
        <AdminPanel title="Report directory" subtitle="Existing catalogues — not a second generator">
          <div className="admin-leadership-dir">
            {DIRECTORY.map((item) => (
              <Link key={item.href} to={item.href} className="admin-leadership-dir__card">
                <span className="admin-muted">{item.group}</span>
                <strong>{item.label}</strong>
              </Link>
            ))}
          </div>
        </AdminPanel>
      ) : null}
    </div>
  )
}
