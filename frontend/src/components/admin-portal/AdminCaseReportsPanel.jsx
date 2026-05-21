import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminReportDetailDrawer } from './AdminReportDetailDrawer.jsx'
import './admin-reports.css'

function statusPillClass(status) {
  const key = String(status || '').toLowerCase()
  return `admin-reports__status-pill admin-reports__status-pill--${key}`
}

export function AdminCaseReportsPanel({ caseId, highlightReportId, highlightType }) {
  const { can } = useAuth()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [drawer, setDrawer] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const qs = `?case_id=${caseId}&page_size=50`
      const [monthly, observation] = await Promise.all([
        apiFetch(`/api/v1/admin/reports/monthly${qs}`).catch(() => ({ items: [] })),
        apiFetch(`/api/v1/admin/reports/observation${qs}`).catch(() => ({ items: [] })),
      ])
      const merged = [...(monthly.items || []), ...(observation.items || [])].sort(
        (a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0),
      )
      setRows(merged)
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!highlightReportId || !highlightType || loading) return
    setDrawer({ reportId: Number(highlightReportId), reportType: highlightType })
  }, [highlightReportId, highlightType, loading])

  function openReview(row) {
    setDrawer({ reportId: row.id, reportType: row.report_type })
  }

  function hubLink(row) {
    const p = new URLSearchParams({
      reportId: String(row.id),
      type: row.report_type,
      case_id: String(caseId),
    })
    return `/admin/reports?${p.toString()}`
  }

  return (
    <section>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <p style={{ margin: 0, fontSize: '0.9rem', color: '#64748b' }}>
          Monthly and observation reports for this case.
        </p>
        <Link to={`/admin/reports?case_id=${caseId}`} className="admin-btn admin-btn--ghost admin-btn--sm">
          Open report management
        </Link>
      </div>

      {loading ? (
        <p>Loading reports…</p>
      ) : rows.length === 0 ? (
        <p className="admin-empty">No reports for this case yet.</p>
      ) : (
        <ul className="admin-queue">
          {rows.map((r) => {
            const highlighted =
              highlightReportId &&
              String(r.id) === String(highlightReportId) &&
              (!highlightType || highlightType === r.report_type)
            return (
              <li
                key={`${r.report_type}-${r.id}`}
                className="admin-queue__item"
                style={highlighted ? { borderColor: '#3b82f6', background: '#eff6ff' } : undefined}
              >
                <div>
                  <p className="admin-queue__title">
                    {r.label}
                    <span style={{ marginLeft: 8, fontSize: '0.7rem', color: '#64748b' }}>
                      {r.report_type === 'observation' ? 'Observation' : 'Monthly'}
                    </span>
                  </p>
                  <p className="admin-queue__meta">
                    {r.therapist_name || 'Therapist'} ·{' '}
                    {r.updated_at ? new Date(r.updated_at).toLocaleString() : ''}
                  </p>
                  {r.content_preview ? (
                    <p className="admin-queue__meta">{r.content_preview}</p>
                  ) : null}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                  <span className={statusPillClass(r.status)}>{r.status}</span>
                  {can('monthly_report.approve') ? (
                    <button
                      type="button"
                      className="admin-btn admin-btn--primary admin-btn--sm"
                      onClick={() => openReview(r)}
                    >
                      Review
                    </button>
                  ) : (
                    <Link to={hubLink(r)} className="admin-btn admin-btn--ghost admin-btn--sm">
                      View in hub
                    </Link>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {drawer ? (
        <AdminReportDetailDrawer
          reportType={drawer.reportType}
          reportId={drawer.reportId}
          onClose={() => setDrawer(null)}
          onAction={() => {
            setDrawer(null)
            load()
          }}
        />
      ) : null}
    </section>
  )
}
