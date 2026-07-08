import { CASE_DOCUMENT_CATEGORIES, categoryLabel, statusLabel, statusTone } from './caseDocumentCategories.js'
import { formatDisplayDate } from './datetime.js'

export const REPORT_DOC_CATEGORIES = new Set([
  'OBSERVATION_REPORT',
  'CASE_MANAGER_MEETING_REPORT',
  'CLIENT_MONTHLY_REPORT',
  'MONTHLY_PROGRESS_REPORT',
  'IEP_PLAN',
  'INCIDENT_REPORT',
  'TERMINATION_PROGRESS_REPORT',
  'ANNUAL_PROGRESS_REPORT',
])

export const TIME_PERIOD_FILTERS = [
  { id: 'all', label: 'All time' },
  { id: '3m', label: 'Last 3 months' },
  { id: '6m', label: 'Last 6 months' },
  { id: 'ytd', label: 'This year' },
]

export const REPORT_TYPE_FILTERS = [
  { id: 'all', label: 'All report types' },
  ...CASE_DOCUMENT_CATEGORIES.filter((c) => REPORT_DOC_CATEGORIES.has(c.value)).map((c) => ({
    id: c.value,
    label: c.label,
  })),
]

function parseItemDate(item) {
  if (item.report_month) {
    const d = new Date(`${item.report_month}-01T12:00:00`)
    if (!Number.isNaN(d.getTime())) return d
  }
  if (item.created_at) {
    const d = new Date(item.created_at)
    if (!Number.isNaN(d.getTime())) return d
  }
  return null
}

export function matchesTimePeriod(item, period) {
  if (period === 'all' || item.kind === 'prompt') return true
  const date = parseItemDate(item)
  if (!date) return true
  const now = new Date()
  if (period === 'ytd') return date.getFullYear() === now.getFullYear()
  const months = period === '3m' ? 3 : period === '6m' ? 6 : 0
  if (!months) return true
  const cutoff = new Date(now.getFullYear(), now.getMonth() - months, now.getDate())
  return date >= cutoff
}

export function matchesReportType(item, reportType) {
  if (reportType === 'all') return true
  if (item.kind === 'prompt') return item.section === 'reports'
  if (!REPORT_DOC_CATEGORIES.has(item.category)) return true
  return item.category === reportType
}

function truncateUrl(url, max = 48) {
  if (!url) return ''
  if (url.length <= max) return url
  return `${url.slice(0, max - 1)}…`
}

export function documentSection(doc) {
  if (REPORT_DOC_CATEGORIES.has(doc.category)) return 'reports'
  if (doc.category === 'SESSION_EVIDENCE') return 'evidence'
  return 'uploads'
}

export function fileKind(doc) {
  const mime = doc.current_version?.mime_type || ''
  const name = (doc.current_version?.file_name || doc.title || '').toLowerCase()
  if (doc.current_version?.source_type === 'EXTERNAL_LINK') return 'link'
  if (mime.includes('pdf') || name.endsWith('.pdf')) return 'pdf'
  if (mime.startsWith('image/') || /\.(png|jpe?g|gif|webp|heic)$/i.test(name)) return 'image'
  if (categoryLabel(doc.category).toLowerCase().includes('assessment')) return 'assessment'
  return 'file'
}

export function fileIcon(kind) {
  const map = {
    pdf: 'picture_as_pdf',
    image: 'image',
    link: 'link',
    assessment: 'analytics',
    file: 'draft',
  }
  return map[kind] || 'draft'
}

export function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function canDeleteDocument(doc, userId) {
  if (!doc?.id || doc.kind === 'prompt') return false
  if (REPORT_DOC_CATEGORIES.has(doc.category)) return false
  if (!['SESSION_EVIDENCE', 'OTHER'].includes(doc.category)) return false
  if (doc.submitted_by_user_id !== userId) return false
  return ['DRAFT', 'CHANGES_REQUESTED'].includes(doc.status)
}

export function needsAttention(doc) {
  if (doc.kind === 'prompt') return true
  return ['CHANGES_REQUESTED', 'DRAFT', 'CM_REVIEW', 'SUBMITTED'].includes(doc.status)
}

export function buildDocumentPrompts({ caseId, qualitySummary, childName }) {
  const base = `/therapist/cases/${caseId}`
  const prompts = []
  const timeline = qualitySummary?.report_timeline || []

  timeline.forEach((row) => {
    const status = String(row.status || '').toUpperCase()
    if (!['DRAFT', 'UNDER_REVIEW', 'REJECTED', 'NOT_STARTED'].includes(status)) return
    const month = row.month || 'Report'
    prompts.push({
      id: `prompt-report-${row.id || month}`,
      kind: 'prompt',
      section: 'reports',
      title: `${month} monthly report`,
      subtitle:
        status === 'NOT_STARTED'
          ? `Start the monthly report for ${childName || 'this client'}.`
          : status === 'REJECTED'
            ? 'Revision requested — review CM notes and resubmit.'
            : status === 'UNDER_REVIEW'
              ? 'Waiting for case manager review.'
              : 'Continue drafting this report.',
      status,
      statusLabel: status === 'NOT_STARTED' ? 'Create' : status === 'REJECTED' ? 'Revise' : 'Review',
      action: {
        label: status === 'NOT_STARTED' ? 'Create report' : 'Open report',
        to: `${base}?tab=reports&section=${status === 'NOT_STARTED' ? 'monthly' : 'dashboard'}`,
      },
    })
  })

  const iepStatus = qualitySummary?.documentation_status
  if (iepStatus && iepStatus !== 'complete') {
    prompts.push({
      id: 'prompt-iep',
      kind: 'prompt',
      section: 'reports',
      title: 'IEP documentation',
      subtitle: 'Goals and strategies still need to be linked before reports can be finalised.',
      status: 'DRAFT',
      statusLabel: 'Build',
      action: { label: 'Open IEP', to: `${base}?tab=reports&section=iep` },
    })
  }

  const missingEvidence = qualitySummary?.evidence_summary?.sessions_without_goal_entries || 0
  if (missingEvidence > 0) {
    prompts.push({
      id: 'prompt-evidence-gap',
      kind: 'prompt',
      section: 'evidence',
      title: `${missingEvidence} session${missingEvidence === 1 ? '' : 's'} need evidence`,
      subtitle: 'Add structured goal notes or upload a session photo.',
      status: 'ATTENTION',
      statusLabel: 'Action',
      action: { label: 'Review logs', to: `${base}?tab=logs` },
      secondaryAction: { label: 'Upload photo', intent: 'upload-evidence' },
    })
  }

  if ((qualitySummary?.evidence_summary?.total_evidence_events || 0) === 0) {
    prompts.push({
      id: 'prompt-first-evidence',
      kind: 'prompt',
      section: 'evidence',
      title: 'Add first session evidence',
      subtitle: 'Upload a photo or note from a recent visit to build the evidence library.',
      status: 'DRAFT',
      statusLabel: 'Upload',
      action: { label: 'Upload evidence', intent: 'upload-evidence' },
    })
  }

  return prompts
}

export function driveStats(docs, prompts) {
  const files = docs.filter((d) => d.kind !== 'prompt')
  return {
    total: files.length,
    reports: files.filter((d) => documentSection(d) === 'reports').length,
    evidence: files.filter((d) => documentSection(d) === 'evidence').length,
    pending: files.filter((d) => ['DRAFT', 'CM_REVIEW', 'SUBMITTED', 'CHANGES_REQUESTED'].includes(d.status)).length,
    attention: prompts.length + files.filter(needsAttention).length,
  }
}

export function normalizeDriveDoc(doc) {
  const kind = fileKind(doc)
  const externalUrl = doc.current_version?.external_url || ''
  const metaParts =
    kind === 'link'
      ? [
          categoryLabel(doc.category),
          truncateUrl(externalUrl),
          doc.report_month ? formatDisplayDate(`${doc.report_month}-01`) : null,
          doc.created_at ? formatDisplayDate(doc.created_at) : null,
        ]
      : [
          categoryLabel(doc.category),
          doc.report_month ? formatDisplayDate(`${doc.report_month}-01`) : null,
          doc.current_version?.file_name,
          formatFileSize(doc.current_version?.size_bytes),
          doc.created_at ? formatDisplayDate(doc.created_at) : null,
        ]
  return {
    ...doc,
    kind: 'file',
    section: documentSection(doc),
    fileKind: kind,
    icon: fileIcon(kind),
    externalUrl,
    meta: metaParts.filter(Boolean).join(' · '),
    statusText: statusLabel(doc.status),
    statusTone: statusTone(doc.status),
  }
}

export function groupDriveItems(items) {
  const reports = items.filter((i) => (i.kind === 'prompt' ? i.section === 'reports' : i.section === 'reports'))
  const evidence = items.filter((i) =>
    i.kind === 'prompt'
      ? i.section === 'evidence'
      : i.fileKind !== 'link' && (i.section === 'evidence' || i.section === 'uploads'),
  )
  const links = items.filter((i) => i.kind !== 'prompt' && i.fileKind === 'link')

  return [
    { id: 'reports', title: 'Reports', items: reports },
    { id: 'evidence', title: 'Session evidence', items: evidence },
    { id: 'links', title: 'Links', items: links },
  ]
}
