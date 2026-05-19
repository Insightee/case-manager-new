/** Map API monthly reports + assigned cases into Monthly Reports UI sections. */

function currentMonthLabel() {
  return new Date().toLocaleString('en-US', { month: 'short', year: 'numeric' })
}

function formatRelative(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins || 1} min ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  const days = Math.floor(hrs / 24)
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  return d.toLocaleDateString()
}

function mapStatusForCard(status) {
  const s = String(status || '').toUpperCase()
  if (s === 'UNDER_REVIEW') return 'under_review'
  if (s === 'PUBLISHED') return 'published'
  if (s === 'DRAFT') return 'draft'
  if (s === 'REJECTED') return 'rejected'
  return s.toLowerCase()
}

function toCard(report) {
  return {
    id: report.id,
    caseId: report.case_code || `Case #${report.case_id}`,
    caseDbId: report.case_id,
    child: report.child_name || '—',
    month: report.month,
    status: mapStatusForCard(report.status),
    apiStatus: report.status,
    summary: report.summary,
    reviewerComment: report.reviewer_comment,
    lastUpdated: formatRelative(report.updated_at || report.created_at),
    dueInfo: report.reviewer_comment
      ? `Admin: ${report.reviewer_comment}`
      : report.status === 'REJECTED'
        ? 'Resubmit after edits'
        : undefined,
  }
}

export function buildReportWorkbench({ reports = [], cases = [] }) {
  const monthLabel = currentMonthLabel()
  const reportMonthsByCase = new Map()
  for (const r of reports) {
    if (!reportMonthsByCase.has(r.case_id)) reportMonthsByCase.set(r.case_id, new Set())
    reportMonthsByCase.get(r.case_id).add(r.month)
  }

  const attention = []
  const inProgress = []
  const published = []

  for (const r of reports) {
    const card = toCard(r)
    const st = String(r.status || '').toUpperCase()
    if (st === 'REJECTED') {
      attention.push({ ...card, attentionType: 'rejected', statusLabel: 'Rejected' })
    } else if (st === 'DRAFT') {
      inProgress.push(card)
    } else if (st === 'UNDER_REVIEW') {
      inProgress.push(card)
    } else if (st === 'PUBLISHED' || st === 'APPROVED') {
      published.push(card)
    }
  }

  for (const c of cases) {
    const months = reportMonthsByCase.get(c.id)
    if (!months || !months.has(monthLabel)) {
      attention.push({
        id: `missing-${c.id}`,
        caseId: c.case_code,
        caseDbId: c.id,
        child: c.child_name || '—',
        month: monthLabel,
        attentionType: 'not_started',
        statusLabel: 'Not started',
        dueInfo: 'No report started for this month',
        isPlaceholder: true,
      })
    }
  }

  const pipeline = {
    draft: inProgress.filter((r) => r.status === 'draft').length,
    underReview: inProgress.filter((r) => r.status === 'under_review').length,
    published: published.length,
    overdue: attention.filter((a) => a.attentionType === 'overdue').length,
  }

  return { attention, inProgress, published, pipeline, monthLabel }
}
