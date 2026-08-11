import { useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { staffDepartmentLabel } from '../../lib/staffDepartments.js'

export function TicketEscalatePicker({ apiBase, disabled, busy, onEscalate, canEscalate }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedDept, setSelectedDept] = useState(null)
  const [loading, setLoading] = useState(false)
  const [targets, setTargets] = useState({ departments: [], staff: [] })
  const [error, setError] = useState('')
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    let cancelled = false
    setLoading(true)
    setError('')
    apiFetch(`${apiBase}/escalation-targets`)
      .then((data) => {
        if (!cancelled) setTargets(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load staff')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, apiBase])

  const searchTerm = search.trim().toLowerCase()

  const searchResults = useMemo(() => {
    if (!searchTerm) return []
    return (targets.staff || []).filter((u) => {
      const hay = `${u.full_name || ''} ${u.email || ''}`.toLowerCase()
      return hay.includes(searchTerm)
    })
  }, [targets.staff, searchTerm])

  const deptStaff = useMemo(() => {
    if (!selectedDept) return []
    return (targets.staff || []).filter((u) => String(u.department || '').toUpperCase() === selectedDept)
  }, [targets.staff, selectedDept])

  const selectedDeptLabel = useMemo(() => {
    if (!selectedDept) return null
    const fromApi = (targets.departments || []).find((d) => d.id === selectedDept)
    return fromApi?.label || staffDepartmentLabel(selectedDept)
  }, [selectedDept, targets.departments])

  function close() {
    setOpen(false)
    setSearch('')
    setSelectedDept(null)
    setError('')
  }

  async function escalatePerson(userId) {
    setError('')
    try {
      await onEscalate?.({ assign_to_user_id: userId })
      close()
    } catch (err) {
      setError(err.message || 'Could not escalate')
    }
  }

  async function escalateDepartment(deptId) {
    setError('')
    try {
      await onEscalate?.({ escalate_to_department: deptId })
      close()
    } catch (err) {
      setError(err.message || 'Could not escalate')
    }
  }

  if (!canEscalate) return null

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        className="admin-btn admin-btn--ghost admin-btn--sm"
        disabled={disabled || busy}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        Escalate to ▾
      </button>
      {open ? (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            marginBottom: 6,
            width: 'min(520px, 92vw)',
            maxHeight: 420,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            boxShadow: '0 12px 32px rgba(15,23,42,0.14)',
            zIndex: 30,
          }}
        >
          <div style={{ padding: '10px 12px', borderBottom: '1px solid #e2e8f0' }}>
            <label style={{ display: 'block', fontSize: '0.68rem', fontWeight: 700, color: '#64748b', marginBottom: 4 }}>
              Search staff
            </label>
            <input
              className="admin-input"
              type="search"
              placeholder="Name or email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
              style={{ width: '100%' }}
            />
          </div>

          {loading ? (
            <p className="admin-muted" style={{ padding: 12, margin: 0, fontSize: '0.8rem' }}>
              Loading staff…
            </p>
          ) : searchTerm ? (
            <div style={{ overflowY: 'auto', padding: 8, flex: 1 }}>
              {searchResults.length === 0 ? (
                <p className="admin-muted" style={{ margin: 8, fontSize: '0.78rem' }}>No staff match your search.</p>
              ) : (
                searchResults.map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    className="admin-btn admin-btn--ghost admin-btn--sm"
                    style={{ width: '100%', justifyContent: 'flex-start', marginBottom: 4 }}
                    disabled={busy}
                    onClick={() => escalatePerson(u.id)}
                  >
                    <span>{u.full_name}</span>
                    <span style={{ color: '#94a3b8', marginLeft: 8, fontSize: '0.72rem' }}>
                      {u.department_label || staffDepartmentLabel(u.department) || 'No department'}
                    </span>
                  </button>
                ))
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', minHeight: 220, flex: 1, overflow: 'hidden' }}>
              <div
                style={{
                  width: '38%',
                  borderRight: '1px solid #e2e8f0',
                  overflowY: 'auto',
                  padding: 6,
                }}
              >
                {(targets.departments || []).map((dept) => {
                  const active = selectedDept === dept.id
                  return (
                    <button
                      key={dept.id}
                      type="button"
                      className={`admin-btn admin-btn--ghost admin-btn--sm ${active ? 'is-active' : ''}`}
                      style={{
                        width: '100%',
                        justifyContent: 'space-between',
                        marginBottom: 4,
                        textAlign: 'left',
                        background: active ? '#eef2ff' : undefined,
                      }}
                      onClick={() => setSelectedDept(dept.id)}
                    >
                      <span>{dept.label}</span>
                      <span style={{ color: '#94a3b8', fontSize: '0.68rem' }}>{dept.member_count ?? 0}</span>
                    </button>
                  )
                })}
              </div>
              <div style={{ flex: 1, overflowY: 'auto', padding: 8, display: 'flex', flexDirection: 'column' }}>
                {!selectedDept ? (
                  <p className="admin-muted" style={{ margin: 8, fontSize: '0.78rem' }}>
                    Choose a department to see team members, or search by name above.
                  </p>
                ) : deptStaff.length === 0 ? (
                  <p className="admin-muted" style={{ margin: 8, fontSize: '0.78rem' }}>
                    No active staff tagged in {selectedDeptLabel}.
                  </p>
                ) : (
                  <>
                    {deptStaff.map((u) => (
                      <button
                        key={u.id}
                        type="button"
                        className="admin-btn admin-btn--ghost admin-btn--sm"
                        style={{ width: '100%', justifyContent: 'flex-start', marginBottom: 4 }}
                        disabled={busy}
                        onClick={() => escalatePerson(u.id)}
                      >
                        {u.full_name}
                        <span style={{ color: '#94a3b8', marginLeft: 6, fontSize: '0.72rem' }}>{u.email}</span>
                      </button>
                    ))}
                    <button
                      type="button"
                      className="admin-btn admin-btn--primary admin-btn--sm"
                      style={{ marginTop: 'auto' }}
                      disabled={busy}
                      onClick={() => escalateDepartment(selectedDept)}
                    >
                      Escalate to all in {selectedDeptLabel}
                    </button>
                  </>
                )}
              </div>
            </div>
          )}

          {error ? (
            <p style={{ color: '#b91c1c', fontSize: '0.75rem', margin: '0 12px 8px' }} role="alert">
              {error}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
