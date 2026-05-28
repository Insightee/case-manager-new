import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { ErrorBanner } from '../shared/ErrorBanner.jsx'
import {
  AdminDataList,
  AdminEmptyState,
  AdminPageHeader,
  AdminSearchInput,
  AdminStickyFilterRow,
  AdminTaskCard,
  StatusBadge,
} from '../admin-portal/ui/index.js'

export function HRCasesPage() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await apiFetch('/api/v1/cases?page_size=100')
        setCases(unwrapList(data))
      } catch (err) {
        setCases([])
        setError(err.message || 'Could not load cases')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const filtered = cases.filter((c) => {
    const q = search.trim().toLowerCase()
    return !q || c.case_code?.toLowerCase().includes(q) || c.product_module?.toLowerCase().includes(q)
  })

  return (
    <div className="admin-page">
      <ErrorBanner message={error} />
      <AdminPageHeader
        eyebrow="HR"
        title="Cases"
        subtitle="Read-only overview of active cases across programmes."
      />

      <AdminStickyFilterRow>
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Search case code or programme…" />
      </AdminStickyFilterRow>

      <div className="admin-desktop-only" style={{ marginBottom: 16 }}>
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Search case code or programme…" />
      </div>

      {loading ? (
        <p className="admin-muted">Loading…</p>
      ) : filtered.length === 0 ? (
        <AdminEmptyState
          title="No cases found"
          hints={['Try a different search term', 'Cases appear here once created in the admin portal']}
        />
      ) : (
        <AdminDataList
          desktop={
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Case code</th>
                    <th>Programme</th>
                    <th>Status</th>
                    <th>Region</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <span className="admin-table__primary">{c.case_code}</span>
                      </td>
                      <td>{c.product_module?.replace(/_/g, ' ') || '—'}</td>
                      <td>
                        <StatusBadge status={c.status} />
                      </td>
                      <td>{c.region || '—'}</td>
                      <td>
                        <Link to={`/admin/cases/${c.id}`} className="admin-btn admin-btn--ghost admin-btn--sm">
                          View case →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          }
          mobile={
            <ul className="admin-data-list__cards">
              {filtered.map((c) => (
                <li key={c.id}>
                  <AdminTaskCard
                    title={c.case_code}
                    meta={c.region || 'No region'}
                    badges={
                      <>
                        <StatusBadge status={c.status} />
                        {c.product_module ? (
                          <span className="admin-chip">{c.product_module.replace(/_/g, ' ')}</span>
                        ) : null}
                      </>
                    }
                    actions={
                      <Link to={`/admin/cases/${c.id}`} className="admin-btn admin-btn--primary admin-btn--sm">
                        View case →
                      </Link>
                    }
                  />
                </li>
              ))}
            </ul>
          }
        />
      )}
    </div>
  )
}
