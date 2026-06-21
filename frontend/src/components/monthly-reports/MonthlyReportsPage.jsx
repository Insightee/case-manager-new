import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { generateReportFromLogs } from '../../lib/reportGenerateFromLogs.js'
import { isReportsRevampActive } from '../../lib/reportsRevampFlags.js'
import { unwrapList } from '../../lib/listApi.js'
import { useTherapistHome, useTherapistReportsPipeline } from '../../hooks/useTherapistHome.js'
import { QueryState } from '../shared/QueryState.jsx'
import { CaseReportsPanel } from '../cases/CaseReportsPanel.jsx'
import { CalendarModal } from './CalendarModal.jsx'
import { ChecklistPanel } from './ChecklistPanel.jsx'
import { CreateDraftModal } from './CreateDraftModal.jsx'
import { PipelineStats } from './PipelineStats.jsx'
import { ReportCard } from './ReportCard.jsx'
import { SectionHeader } from './SectionHeader.jsx'
import { ClinicalFloatingActionButton } from '../clinical-ui/ClinicalFloatingActionButton.jsx'
import '../../styles/case-profile-v2.css'

const REPORTS_EDIT_BASE = '/therapist/reports/edit'

function caseMonthlyUrl(caseDbId) {
  if (isReportsRevampActive('therapist') && caseDbId) {
    return `/therapist/cases/${caseDbId}?tab=reports&section=monthly`
  }
  return `/therapist/reports?case_id=${caseDbId}`
}

function reportEditUrl(report) {
  if (isReportsRevampActive('therapist') && report.caseDbId) {
    return `/therapist/cases/${report.caseDbId}/reports/monthly/${report.id}`
  }
  return `${REPORTS_EDIT_BASE}/${report.id}`
}

const DEFAULT_CHECKLIST = [
  { id: 'c1', label: 'Review all session logs for the month', done: false },
  { id: 'c2', label: 'Draft summaries for each active case', done: false },
  { id: 'c3', label: 'Submit reports for admin review', done: false },
  { id: 'c4', label: 'Respond to any rejected reports', done: false },
]

const FILTER_CHIPS = [
  { id: 'all',       label: 'All' },
  { id: 'overdue',   label: 'Pending logs' },
  { id: 'draft',     label: 'Draft' },
  { id: 'underReview', label: 'Under review' },
  { id: 'published', label: 'Published' },
]

function Toast({ message, visible, onDismiss }) {
  if (!visible) return null
  return (
    <div
      role="status"
      style={{
        position: 'fixed', right: '1rem', top: '1rem', zIndex: 100,
        display: 'flex', alignItems: 'flex-start', gap: '0.75rem',
        maxWidth: '360px', background: '#fff', borderRadius: '14px',
        border: '1px solid var(--clinical-green-soft)', padding: '0.875rem 1rem',
        boxShadow: 'var(--clinical-shadow-panel)',
      }}
    >
      <span style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--clinical-green-soft)', color: 'var(--clinical-green)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, flexShrink: 0 }}>✓</span>
      <div style={{ flex: 1 }}>
        <p style={{ fontWeight: 700, color: '#0f172a', margin: '0 0 0.15rem', fontSize: '0.875rem' }}>Done</p>
        <p style={{ fontSize: '0.8125rem', color: 'var(--clinical-muted)', margin: 0 }}>{message}</p>
      </div>
      <button type="button" onClick={onDismiss} aria-label="Dismiss" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--clinical-muted)', fontSize: '1.125rem', padding: 0, lineHeight: 1 }}>×</button>
    </div>
  )
}

function matchesSearch(item, q) {
  if (!q.trim()) return true
  const s = q.toLowerCase()
  return (
    item.caseId.toLowerCase().includes(s) ||
    item.child.toLowerCase().includes(s) ||
    item.month.toLowerCase().includes(s)
  )
}

function matchesCaseFilter(item, caseDbId) {
  if (!caseDbId) return true
  return item.caseDbId === Number(caseDbId)
}

function SectionBlock({ id, title, subtitle, urgency = false, children }) {
  return (
    <section aria-labelledby={id}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.625rem' }}>
        <span
          style={{
            width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
            background: urgency ? 'var(--clinical-red)' : 'var(--clinical-amber)',
          }}
          aria-hidden
        />
        <h3 id={id} style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a', margin: 0 }}>{title}</h3>
      </div>
      {subtitle ? <p style={{ fontSize: '0.8125rem', color: 'var(--clinical-muted)', margin: '0 0 0.875rem' }}>{subtitle}</p> : null}
      {children}
    </section>
  )
}

export function MonthlyReportsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const caseFilterId = searchParams.get('case_id')
  const openCreate = searchParams.get('create') === '1'
  const [assignedCases, setAssignedCases] = useState([])
  const [search, setSearch] = useState('')
  const [pipelineFilter, setPipelineFilter] = useState('all')
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [draftOpen, setDraftOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [workbench, setWorkbench] = useState({
    attention: [],
    inProgress: [],
    published: [],
    pipeline: { draft: 0, underReview: 0, published: 0, overdue: 0 },
    monthLabel: '',
  })
  const [checklist, setChecklist] = useState(DEFAULT_CHECKLIST.map((c) => ({ ...c })))
  const [toast, setToast] = useState({ visible: false, message: '' })

  const showToast = useCallback((message) => {
    setToast({ visible: true, message })
    window.setTimeout(() => setToast((t) => ({ ...t, visible: false })), 3800)
  }, [])

  const { data: pipelineData, isLoading: pipeLoading, isError, error: fetchError, refetch } =
    useTherapistReportsPipeline()
  const { data: homeData } = useTherapistHome()

  useEffect(() => {
    if (pipelineData) {
      setWorkbench({
        attention: pipelineData.attention || [],
        inProgress: pipelineData.in_progress || [],
        published: pipelineData.published || [],
        pipeline: pipelineData.pipeline || { draft: 0, underReview: 0, published: 0, overdue: 0 },
        monthLabel: pipelineData.month_label || '',
      })
    }
    if (homeData?.cases_board?.allCases) {
      setAssignedCases(
        homeData.cases_board.allCases.map((c) => ({
          id: c.id,
          case_code: c.caseId,
          child_name: c.child,
        })),
      )
    }
    setLoading(pipeLoading)
    if (isError) setError(fetchError?.message || 'Could not load reports')
    else setError('')
  }, [pipelineData, homeData, pipeLoading, isError, fetchError])

  const load = useCallback(() => refetch(), [refetch])

  useEffect(() => {
    if (openCreate && caseFilterId) {
      setDraftOpen(true)
    }
  }, [openCreate, caseFilterId])

  const filteredCase = useMemo(() => {
    if (!caseFilterId) return null
    const id = Number(caseFilterId)
    if (!Number.isFinite(id)) return null
    const found = assignedCases.find((c) => c.id === id)
    if (found) return found
    return { id, child_name: 'Client', case_code: `Case #${id}` }
  }, [assignedCases, caseFilterId])

  function clearCaseFilter() {
    setSearchParams({})
  }

  function goToCaseReports(caseDbId, { create = false } = {}) {
    const params = new URLSearchParams()
    params.set('case_id', String(caseDbId))
    if (create) params.set('create', '1')
    setSearchParams(params)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handlePipelineClick = useCallback((key) => {
    setPipelineFilter((prev) => (prev === key ? 'all' : key))
  }, [])

  async function handleSubmitReview(report) {
    if (report.isPlaceholder) { setDraftOpen(true); return }
    try {
      await apiFetch(`/api/v1/reports/monthly/${report.id}/submit`, { method: 'POST' })
      showToast(`Submitted ${report.caseId} (${report.month}) for review.`)
      await load()
    } catch (err) {
      showToast(err.message || 'Could not submit report')
    }
  }

  async function handleGenerateFromLogs(report) {
    if (report.isPlaceholder || !report.id || String(report.id).startsWith('missing-')) {
      showToast('Create a report draft for this case first.')
      return
    }
    try {
      await generateReportFromLogs(report.id, 'replace')
      showToast(`Draft built from session logs — ${report.child || report.caseId}.`)
      navigate(reportEditUrl(report))
    } catch (err) {
      showToast(err.message || 'Could not generate from session logs')
    }
  }

  const q = search.trim()

  const filteredAttention = useMemo(() => {
    let list = workbench.attention.filter((a) => matchesSearch(a, q) && matchesCaseFilter(a, caseFilterId))
    if (pipelineFilter === 'overdue') list = list.filter((a) => a.attentionType === 'overdue')
    return list
  }, [workbench.attention, q, pipelineFilter, caseFilterId])

  const filteredInProgress = useMemo(() => {
    let list = workbench.inProgress.filter((r) => matchesSearch(r, q) && matchesCaseFilter(r, caseFilterId))
    if (pipelineFilter === 'draft') list = list.filter((r) => r.status === 'draft')
    if (pipelineFilter === 'underReview') list = list.filter((r) => r.status === 'under_review')
    return list
  }, [workbench.inProgress, q, pipelineFilter, caseFilterId])

  const filteredPublished = useMemo(() => {
    return workbench.published.filter((r) => matchesSearch(r, q) && matchesCaseFilter(r, caseFilterId))
  }, [workbench.published, q, caseFilterId])

  const showAttentionSection = pipelineFilter === 'all' || pipelineFilter === 'overdue'
  const showProgressSection = pipelineFilter === 'all' || pipelineFilter === 'draft' || pipelineFilter === 'underReview'
  const showPublishedSection = pipelineFilter === 'all' || pipelineFilter === 'published'

  const totalVisible = useMemo(() => {
    let n = 0
    if (showAttentionSection) n += filteredAttention.length
    if (showProgressSection) n += filteredInProgress.length
    if (showPublishedSection) n += filteredPublished.length
    return n
  }, [showAttentionSection, showProgressSection, showPublishedSection, filteredAttention.length, filteredInProgress.length, filteredPublished.length])

  const handleCheckToggle = (id) => {
    setChecklist((prev) => prev.map((i) => (i.id === id ? { ...i, done: !i.done } : i)))
  }

  if (loading) {
    return (
      <div className="clinical-reports-home__main">
        <p className="ic-case-panel__loading">Loading monthly reports…</p>
      </div>
    )
  }

  return (
    <div style={{ background: 'var(--clinical-page-bg)', minHeight: '100%', padding: '0 0 6rem' }}>
      <Toast
        message={toast.message}
        visible={toast.visible}
        onDismiss={() => setToast((t) => ({ ...t, visible: false }))}
      />

      <CreateDraftModal
        open={draftOpen}
        onClose={() => {
          setDraftOpen(false)
          if (openCreate) {
            const params = new URLSearchParams(searchParams)
            params.delete('create')
            setSearchParams(params)
          }
        }}
        defaultMonth={workbench.monthLabel}
        defaultCaseId={caseFilterId ? Number(caseFilterId) : null}
        onCreated={() => {
          showToast('Draft saved — continue editing or submit for review.')
          load()
        }}
      />

      <CalendarModal open={calendarOpen} onClose={() => setCalendarOpen(false)} events={[]} />

      <div className="clinical-reports-home__main">
        {/* Page header */}
        <div className="clinical-reports-home__header">
          <h1 className="clinical-reports-home__title">
            {filteredCase ? `Reports · ${filteredCase.child_name}` : 'Reports Home'}
          </h1>
          <p className="clinical-reports-home__subtitle">
            {filteredCase
              ? 'Draft, submit, and track monthly progress for this client.'
              : 'Manage and monitor clinical report documentation across your cases.'}
          </p>
        </div>

        {/* Case filter banner */}
        {filteredCase ? (
          <div className="cp-hint cp-hint--warn" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
            <p style={{ margin: 0, fontWeight: 600 }}>
              Showing: <strong>{filteredCase.child_name}</strong> · {filteredCase.case_code}
            </p>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <Link
                to={`/therapist/cases/${filteredCase.id}`}
                className="clinical-btn-primary"
                style={{ fontSize: '0.8125rem', minHeight: '36px', padding: '0.375rem 0.875rem' }}
              >
                Open case
              </Link>
              <button
                type="button"
                onClick={clearCaseFilter}
                className="clinical-btn-secondary"
                style={{ fontSize: '0.8125rem', minHeight: '36px', padding: '0.375rem 0.875rem' }}
              >
                All clients
              </button>
            </div>
          </div>
        ) : null}

        {/* Search + create */}
        <div className="clinical-reports-home__toolbar">
          <div className="clinical-search clinical-reports-home__toolbar-search">
            <span className="clinical-search__icon" aria-hidden="true">🔍</span>
            <input
              className="clinical-search__input"
              type="search"
              placeholder="Search case, child, or month…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search reports"
            />
          </div>
          <button
            type="button"
            className="clinical-btn-primary"
            onClick={() => setDraftOpen(true)}
            style={{ flexShrink: 0 }}
          >
            + Create Draft
          </button>
        </div>

        {/* Filter chips */}
        <div className="clinical-filter-chips">
          {FILTER_CHIPS.map((chip) => (
            <button
              key={chip.id}
              type="button"
              className={`clinical-filter-chip${pipelineFilter === chip.id ? ' is-active' : ''}`}
              onClick={() => setPipelineFilter(chip.id)}
            >
              {chip.label}
            </button>
          ))}
        </div>

        {/* Pipeline stats */}
        <section aria-label="Pipeline overview" style={{ marginBottom: '1.25rem' }}>
          <h3 className="sr-only">Report pipeline overview</h3>
          <PipelineStats
            counts={workbench.pipeline}
            activeFilter={pipelineFilter === 'all' ? null : pipelineFilter}
            onFilter={handlePipelineClick}
          />
        </section>

        {filteredCase ? (
          <CaseReportsPanel
            caseId={filteredCase.id}
            caseCode={filteredCase.case_code}
            childName={filteredCase.child_name}
            onUpdated={load}
          />
        ) : null}

        {error ? <p className="ic-case-panel__error">{error}</p> : null}

        <div style={{ display: 'grid', gap: '1.5rem', gridTemplateColumns: '1fr', alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', minWidth: 0 }}>
            {caseFilterId ? null : totalVisible === 0 ? (
              <div className="clinical-empty-state cp-card">
                <p className="clinical-empty-state__title">
                  {q || pipelineFilter !== 'all'
                    ? 'No reports match your search or filters'
                    : 'No reports yet'}
                </p>
                <p className="clinical-empty-state__body">
                  {q || pipelineFilter !== 'all'
                    ? 'Try clearing the filter or widening your search.'
                    : 'Create a draft to start your first monthly report, or open a case from My Cases.'}
                </p>
                {!q && pipelineFilter === 'all' ? (
                  <button
                    type="button"
                    className="clinical-btn-primary"
                    onClick={() => setDraftOpen(true)}
                    style={{ marginTop: '0.75rem' }}
                  >
                    Create draft
                  </button>
                ) : null}
              </div>
            ) : (
              <>
                {showAttentionSection && (
                  <SectionBlock id="attention-heading" title="Attention required" subtitle="Missing this month, rejected, or overdue." urgency>
                    {filteredAttention.length === 0 ? (
                      <div className="clinical-empty-state" style={{ background: '#fff', border: '1px dashed var(--clinical-border)', borderRadius: 'var(--clinical-radius-card)', padding: '1.5rem' }}>
                        <p className="clinical-empty-state__body">Nothing urgent right now — you're on top of it.</p>
                      </div>
                    ) : (
                      <div className="clinical-case-grid">
                        {filteredAttention.map((r) => (
                          <ReportCard
                            key={r.id}
                            variant="attention"
                            report={r}
                            onGenerateFromLogs={handleGenerateFromLogs}
                            onStart={() =>
                              r.isPlaceholder && r.caseDbId ? goToCaseReports(r.caseDbId, { create: true }) : setDraftOpen(true)
                            }
                            onContinue={(rep) => {
                              if (rep.id && !String(rep.id).startsWith('missing-')) navigate(reportEditUrl(rep))
                              else if (rep.caseDbId) goToCaseReports(rep.caseDbId)
                            }}
                          />
                        ))}
                      </div>
                    )}
                  </SectionBlock>
                )}

                {showProgressSection && (
                  <SectionBlock id="in-progress-heading" title="In progress" subtitle="Drafts and items under review.">
                    {filteredInProgress.length === 0 ? (
                      <div className="clinical-empty-state" style={{ background: '#fff', border: '1px dashed var(--clinical-border)', borderRadius: 'var(--clinical-radius-card)', padding: '1.5rem' }}>
                        <p className="clinical-empty-state__body">No reports in this stage for the current filter.</p>
                      </div>
                    ) : (
                      <div className="clinical-case-grid">
                        {filteredInProgress.map((r) => (
                          <ReportCard
                            key={r.id}
                            variant="progress"
                            report={r}
                            onGenerateFromLogs={handleGenerateFromLogs}
                            onContinue={(rep) => navigate(reportEditUrl(rep))}
                            onSubmitReview={r.status === 'draft' ? handleSubmitReview : undefined}
                            onPreview={(rep) => navigate(reportEditUrl(rep))}
                            onDownload={(rep) =>
                              apiDownload(`/api/v1/reports/monthly/${rep.id}/download`, `report_${rep.month}.pdf`)
                            }
                          />
                        ))}
                      </div>
                    )}
                  </SectionBlock>
                )}

                {showPublishedSection && (
                  <SectionBlock id="published-heading" title="Published" subtitle="Approved and visible to families.">
                    {filteredPublished.length === 0 ? (
                      <div className="clinical-empty-state" style={{ background: '#fff', border: '1px dashed var(--clinical-border)', borderRadius: 'var(--clinical-radius-card)', padding: '1.5rem' }}>
                        <p className="clinical-empty-state__body">No published reports match your search.</p>
                      </div>
                    ) : (
                      <div className="clinical-case-grid">
                        {filteredPublished.map((r) => (
                          <ReportCard
                            key={r.id}
                            variant="published"
                            report={r}
                            onView={(rep) => { if (rep.caseDbId) goToCaseReports(rep.caseDbId) }}
                          />
                        ))}
                      </div>
                    )}
                  </SectionBlock>
                )}
              </>
            )}
          </div>

          <div style={{ gridColumn: '1', marginTop: '0.5rem' }}>
            <ChecklistPanel items={checklist} onToggle={handleCheckToggle} />
            <p style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--clinical-muted)' }}>
              Tip: open a case from{' '}
              <Link to="/therapist/cases" style={{ color: 'var(--clinical-purple)', fontWeight: 600 }}>
                My Cases
              </Link>{' '}
              to jump straight to that client's reports.
            </p>
          </div>
        </div>
      </div>

      <ClinicalFloatingActionButton
        label="Create report"
        onClick={() => setDraftOpen(true)}
        icon="+"
      />
    </div>
  )
}
