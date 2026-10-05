import { AdminStatCard } from './ui/index.js'

const LANDING_HINTS = {
  CASE_MANAGER: 'Case managers land on Workbench.',
  SUPERVISOR: 'Supervisors land on Workbench.',
  FINANCE: 'Finance lands on Invoices.',
}

function kpi(title, value, hint, tone, icon, to, basis = 'Current') {
  return { title, value: value ?? '—', hint, tone, icon, to, basis }
}

export function buildAdminKpis({ summary, role, canNavigate, can }) {
  if (!summary) return []

  const financePrimary = role === 'FINANCE'
  const clinicalPrimary = role === 'CASE_MANAGER' || role === 'SUPERVISOR'
  const showFinanceInvoices = can('invoice.approve') && (!clinicalPrimary || financePrimary)
  const showClinical =
    can('monthly_report.approve') || can('case.update') || can('iep.read')
  const ticketHref = '/admin/support?tab=ticket-report'

  const items = []

  if (!financePrimary) {
    items.push(
      kpi('Active cases', summary.open_cases, `${summary.total_cases ?? '—'} total in system`, 'teal', '◉', '/admin/cases'),
      kpi(
        'Pending allotment',
        summary.pending_allotment,
        'Needs therapist assignment',
        'amber',
        '◎',
        can('case.create') ? '/admin/cases?allot=1' : '/admin/cases?queue=allotment',
      ),
    )
  }

  if (showClinical && can('monthly_report.approve')) {
    items.push(
      kpi(
        'Observation checklists',
        summary.observation_checklists_pending,
        summary.observation_checklists_overdue
          ? `${summary.observation_checklists_overdue} overdue (due date set)`
          : 'Awaiting CM review',
        'indigo',
        '☑',
        '/admin/workbench?section=observations',
      ),
      kpi(
        'Reports in review',
        summary.reports_in_review,
        summary.observation_reports_in_review
          ? `${summary.observation_reports_in_review} observation reports`
          : 'Awaiting approval',
        'indigo',
        '▣',
        '/admin/reports?tab=queue',
      ),
    )
  } else if (!financePrimary && can('monthly_report.approve')) {
    items.push(
      kpi('Reports in review', summary.reports_in_review, 'Awaiting approval', 'indigo', '▣', '/admin/reports?tab=queue'),
    )
  }

  if (showClinical && can('case.update')) {
    items.push(
      kpi(
        'Status requests',
        summary.status_requests_pending,
        'Case lifecycle changes',
        'amber',
        '↔',
        '/admin/workbench?section=status_requests',
      ),
    )
  }

  if (can('iep.read') && showClinical) {
    items.push(
      kpi(
        'IEP attention',
        summary.iep_attention,
        summary.iep_plans_draft ? `${summary.iep_plans_draft} draft plan(s)` : 'Structured + attachments',
        'indigo',
        '📋',
        '/admin/iep',
      ),
    )
  }

  if (showFinanceInvoices) {
    items.push(
      kpi('Therapist invoices', summary.invoices_pending, 'Payout approval queue', 'rose', '₹', '/admin/therapist-payouts?sub=payouts'),
    )
  }

  if (can('invoice.approve') && (financePrimary || canNavigate)) {
    items.push(
      kpi(
        'Client payment claims',
        summary.client_payments_pending_review,
        'Family-submitted payments',
        'rose',
        '💳',
        '/admin/invoices?tab=payments',
      ),
    )
  }

  if (!financePrimary && can('ticket.manage')) {
    items.push(
      kpi(
        'Open tickets',
        summary.open_tickets,
        summary.in_progress_tickets
          ? `${summary.in_progress_tickets} in progress · needs action ${summary.tickets_needing_action ?? ''}`
          : 'Open now (in progress counted separately)',
        'slate',
        '✉',
        ticketHref,
      ),
    )
  }

  if (!financePrimary && !clinicalPrimary) {
    items.push(
      kpi('Suspended', summary.suspended_cases, `${summary.closed_cases ?? '—'} closed`, 'slate', '⏸', '/admin/cases'),
    )
  }

  if (!canNavigate) {
    return items.map((item) => ({ ...item, to: undefined }))
  }
  return items
}

export function AdminOpsKpiGrid({ kpis, loading }) {
  return (
    <section className="admin-kpi-grid" aria-label="Key metrics">
      {loading
        ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="admin-skeleton" />)
        : kpis.map((kpiItem) => (
            <AdminStatCard
              key={kpiItem.title}
              title={kpiItem.title}
              value={kpiItem.value}
              hint={kpiItem.hint}
              tone={kpiItem.tone}
              icon={kpiItem.icon}
              to={kpiItem.to}
              basis={kpiItem.basis}
            />
          ))}
    </section>
  )
}

export function adminLandingHint(role) {
  return LANDING_HINTS[role] || null
}
