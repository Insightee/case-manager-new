import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../../lib/apiClient.js'
import { unwrapList } from '../../../lib/listApi.js'
import { ClinicalCard } from '../../clinical-ui/ClinicalCard.jsx'
import { ClinicalStatusBadge } from '../../clinical-ui/ClinicalStatusBadge.jsx'

function reportTypeLabel(category) {
  const c = String(category || '').toLowerCase()
  if (c === 'progress') return 'Progress Report'
  return 'Monthly Report'
}

export function CaseReportHistorySection({ caseId, caseCode, childName, variant = 'therapist' }) {
  const [workbench, setWorkbench] = useState(null)
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const editBase =
    variant === 'admin' ? '/admin/reports/edit' : `/therapist/cases/${caseId}/reports/monthly`

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [wb, rows] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}/reports-workbench`),
        apiFetch('/api/v1/reports/monthly?page_size=100'),
      ])
      setWorkbench(wb)
      setReports(unwrapList(rows).filter((r) => r.case_id === Number(caseId)))
    } catch (err) {
      setError(err.message || 'Could not load report history.')
      setWorkbench(null)
      setReports([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const timeline = useMemo(() => {
    const items = []
    const obs = workbench?.observation
    if (obs) {
      items.push({
        key: 'observation',
        type: 'Observation Report',
        title: 'Initial observation checklist',
        status: obs.status,
        meta: obs.is_overdue ? 'Overdue' : 'Clinical intake',
        section: 'observation',
      })
    }
    if (workbench?.iep_plan_status) {
      items.push({
        key: 'iep',
        type: 'IEP Report',
        title: 'IEP support plan',
        status: workbench.iep_plan_status,
        meta: 'Support plan',
        section: 'iep',
      })
    }
    for (const r of reports) {
      items.push({
        key: `report-${r.id}`,
        type: reportTypeLabel(r.category),
        title: r.month || r.title || 'Report',
        status: r.status,
        meta: r.summary || caseCode,
        section: String(r.category || '').toLowerCase() === 'progress' ? 'progress' : 'monthly',
        reportId: r.id,
        editable: r.status === 'DRAFT' || r.status === 'REJECTED',
      })
    }
    return items
  }, [workbench, reports, caseCode])

  if (loading) return <p className="ic-case-panel__loading">Loading report history…</p>
  if (error) return <p className="ic-case-panel__error">{error}</p>

  return (
    <div className="cp-report-history">
      <header className="cp-report-history__header">
        <h2 className="clinical-section-heading">Report History</h2>
        <p className="clinical-section-subtitle">
          Past and in-progress reports for <strong>{childName}</strong>.
        </p>
      </header>

      {timeline.length === 0 ? (
        <div className="clinical-empty-state cp-report-history__empty">
          <p className="clinical-empty-state__body">No reports yet for this case.</p>
        </div>
      ) : (
        <ul className="cp-report-history__list">
          {timeline.map((item) => (
            <li key={item.key}>
              <ClinicalCard className="cp-report-history__card">
                <div className="cp-report-history__card-head">
                  <div>
                    <p className="cp-report-history__type">{item.type}</p>
                    <strong className="cp-report-history__title">{item.title}</strong>
                    {item.meta ? <p className="cp-report-history__meta">{item.meta}</p> : null}
                  </div>
                  {item.status ? <ClinicalStatusBadge status={item.status} /> : null}
                </div>
                <div className="cp-report-history__actions">
                  {item.reportId ? (
                    <Link
                      to={`${editBase}/${item.reportId}`}
                      className="clinical-btn-ghost"
                      style={{ fontSize: '0.8125rem', minHeight: '36px' }}
                    >
                      {item.editable ? 'Continue' : 'View report →'}
                    </Link>
                  ) : (
                    <Link
                      to={
                        variant === 'admin'
                          ? `/admin/cases/${caseId}?tab=reports&section=${item.section}`
                          : `/therapist/cases/${caseId}?tab=reports&section=${item.section}`
                      }
                      className="clinical-btn-ghost"
                      style={{ fontSize: '0.8125rem', minHeight: '36px' }}
                    >
                      Open {item.type.replace(' Report', '')} →
                    </Link>
                  )}
                </div>
              </ClinicalCard>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
