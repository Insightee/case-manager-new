import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { IncidentDetailPanel } from '../support/IncidentDetailPanel.jsx'
import { StatusBadge } from './ui/index.js'

export function AdminCaseIncidentsPanel({ caseId, highlightIncidentId }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const qs = new URLSearchParams({ case_id: String(caseId), page_size: '50' })
      setRows(unwrapList(await apiFetch(`/api/v1/incidents?${qs.toString()}`)))
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  async function openIncident(inc) {
    if (expandedId === inc.id) {
      setExpandedId(null)
      setDetail(null)
      return
    }
    setExpandedId(inc.id)
    setDetailLoading(true)
    try {
      setDetail(await apiFetch(`/api/v1/incidents/${inc.id}`))
    } catch {
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => {
    if (!highlightIncidentId || loading || rows.length === 0) return
    const inc = rows.find((r) => String(r.id) === String(highlightIncidentId))
    if (!inc || expandedId === inc.id) return
    openIncident(inc)
  }, [highlightIncidentId, loading, rows])

  function onDetailUpdated(updated) {
    setDetail(updated)
    load()
  }

  return (
    <section>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <p style={{ margin: 0, fontSize: '0.9rem', color: '#64748b' }}>
          Incident reports filed for this case.
        </p>
        <Link to="/admin/support?tab=incidents" className="admin-btn admin-btn--ghost admin-btn--sm">
          Open support hub
        </Link>
      </div>

      {loading ? (
        <p className="admin-muted">Loading incidents…</p>
      ) : rows.length === 0 ? (
        <p className="admin-empty">No incidents for this case yet.</p>
      ) : (
        <ul className="admin-queue">
          {rows.map((inc) => {
            const highlighted = highlightIncidentId && String(inc.id) === String(highlightIncidentId)
            return (
              <li
                key={inc.id}
                className="admin-queue__item"
                style={{
                  flexDirection: 'column',
                  alignItems: 'stretch',
                  ...(highlighted ? { borderColor: '#3b82f6', background: '#eff6ff' } : {}),
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, width: '100%' }}>
                  <button
                    type="button"
                    aria-expanded={expandedId === inc.id}
                    onClick={() => openIncident(inc)}
                    style={{ flex: 1, textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                  >
                    <p className="admin-queue__title">{inc.title}</p>
                    <p className="admin-queue__meta">
                      #{inc.id}
                      {inc.reporter_name ? ` · ${inc.reporter_name}` : ''}
                    </p>
                  </button>
                  <StatusBadge status={inc.status} />
                </div>
                {expandedId === inc.id ? (
                  <div style={{ marginTop: 12, width: '100%' }}>
                    {detailLoading ? (
                      <p className="admin-queue__meta">Loading report…</p>
                    ) : detail ? (
                      <IncidentDetailPanel
                        incident={detail}
                        onUpdated={onDetailUpdated}
                        apiBase="/api/v1/incidents"
                        canManage
                      />
                    ) : null}
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
