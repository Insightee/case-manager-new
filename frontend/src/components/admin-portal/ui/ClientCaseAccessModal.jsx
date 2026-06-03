import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'

export function ClientCaseAccessModal({ family, open, onClose, onSuccess, onError }) {
  const [caseManagers, setCaseManagers] = useState([])
  const [draftCm, setDraftCm] = useState({})
  const [savingId, setSavingId] = useState(null)

  const cases = family?.cases?.filter((c) => c.caseId) || []

  useEffect(() => {
    if (!open) return
    apiFetch('/api/v1/admin/users/directory?roles=CASE_MANAGER,MODULE_ADMIN')
      .then((rows) => setCaseManagers(Array.isArray(rows) ? rows : []))
      .catch(() => setCaseManagers([]))
  }, [open])

  useEffect(() => {
    if (!open || !family) return
    const next = {}
    for (const c of cases) {
      next[c.caseId] = c.caseManagerUserId ? String(c.caseManagerUserId) : ''
    }
    setDraftCm(next)
  }, [open, family, cases.length])

  if (!open || !family) return null

  async function saveCaseCm(caseRow) {
    const cmId = draftCm[caseRow.caseId]
    if (!cmId) {
      onError?.('Select a case manager.')
      return
    }
    setSavingId(caseRow.caseId)
    onError?.('')
    try {
      await apiFetch(`/api/v1/cases/${caseRow.caseId}`, {
        method: 'PATCH',
        body: JSON.stringify({ case_manager_user_id: Number(cmId) }),
      })
      onSuccess?.(`Case manager updated for ${caseRow.caseCode}.`)
    } catch (err) {
      onError?.(err.message || 'Could not update case manager')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="admin-drawer-backdrop" role="presentation" onClick={onClose}>
      <div
        className="admin-drawer admin-drawer--wide"
        role="dialog"
        aria-labelledby="client-case-access-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="admin-drawer__header">
          <h2 id="client-case-access-title" className="admin-drawer__title">
            Edit access — {family.childName}
          </h2>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="admin-drawer__body">
          {cases.length === 0 ? (
            <p className="admin-muted">No cases linked yet. Allot a case from the Cases board.</p>
          ) : (
            <ul className="admin-stack" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {cases.map((c) => (
                <li
                  key={c.caseId}
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 8,
                    alignItems: 'center',
                    padding: '12px 0',
                    borderBottom: '1px solid var(--admin-border, #e2e8f0)',
                  }}
                >
                  <span style={{ minWidth: 120, fontWeight: 600 }}>{c.caseCode}</span>
                  <span className="admin-chip">{c.status || '—'}</span>
                  <select
                    className="admin-input admin-input--sm"
                    value={draftCm[c.caseId] || ''}
                    onChange={(e) => setDraftCm((d) => ({ ...d, [c.caseId]: e.target.value }))}
                    aria-label={`Case manager for ${c.caseCode}`}
                  >
                    <option value="">Select CM…</option>
                    {caseManagers.map((cm) => (
                      <option key={cm.id} value={cm.id}>
                        {cm.full_name || cm.email}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary admin-btn--sm"
                    disabled={savingId === c.caseId}
                    onClick={() => saveCaseCm(c)}
                  >
                    {savingId === c.caseId ? 'Saving…' : 'Save CM'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
