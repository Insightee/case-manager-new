import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import { leaveCreditPendingLabel } from '../../lib/leaveBalanceDisplay.js'
import { caseLabel, caseServiceLine, formatLeaveRecordSplit } from '../../lib/leaveFormUtils.js'
import { TherapistLeaveRequestFields } from '../therapist/TherapistLeaveRequestFields.jsx'
import { StatusBadge } from '../admin-portal/ui/index.js'
import { TherapistLeaveBalancePanel } from './TherapistLeaveBalancePanel.jsx'

const EMPTY_FORM = {
  case_ids: [],
  start_date: '',
  end_date: '',
  reason: '',
  consulted_with_parents: false,
  billing_category: 'PAID',
}

const MIN_SEARCH_LEN = 2

export function ManualLeaveTab({ year: yearProp, onYearChange, onLeaveRecorded }) {
  const year = yearProp || new Date().getFullYear()
  const [therapistSearch, setTherapistSearch] = useState('')
  const [therapistId, setTherapistId] = useState('')
  const [selectedTherapistSnapshot, setSelectedTherapistSnapshot] = useState(null)
  const [cases, setCases] = useState([])
  const [leaves, setLeaves] = useState([])
  const [balance, setBalance] = useState(null)
  const [loadingTherapists, setLoadingTherapists] = useState(false)
  const [loadingContext, setLoadingContext] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [therapistResults, setTherapistResults] = useState([])

  const searchReady = therapistSearch.trim().length >= MIN_SEARCH_LEN

  useEffect(() => {
    if (!searchReady) {
      setTherapistResults([])
      setLoadingTherapists(false)
      return undefined
    }

    const q = encodeURIComponent(therapistSearch.trim())
    let cancelled = false
    setLoadingTherapists(true)
    apiFetch(`/api/v1/hr/therapists?search=${q}`)
      .then((rows) => {
        if (!cancelled) {
          const list = Array.isArray(rows) ? rows : []
          setTherapistResults(list)
        }
      })
      .catch(() => {
        if (!cancelled) setTherapistResults([])
      })
      .finally(() => {
        if (!cancelled) setLoadingTherapists(false)
      })

    return () => {
      cancelled = true
    }
  }, [therapistSearch, searchReady])

  const selectedTherapist = useMemo(() => {
    if (selectedTherapistSnapshot && String(selectedTherapistSnapshot.id) === String(therapistId)) {
      return selectedTherapistSnapshot
    }
    return therapistResults.find((t) => String(t.id) === String(therapistId)) || selectedTherapistSnapshot
  }, [therapistResults, therapistId, selectedTherapistSnapshot])

  const loadContext = useCallback(async () => {
    if (!therapistId) {
      setCases([])
      setLeaves([])
      setBalance(null)
      return
    }
    setLoadingContext(true)
    setError('')
    try {
      const [caseData, leaveRows, bal] = await Promise.all([
        apiFetch(`/api/v1/hr/therapists/${therapistId}/cases`),
        apiFetch(`/api/v1/leave?therapist_id=${therapistId}`),
        apiFetch(`/api/v1/leave/balance/${therapistId}?year=${year}`),
      ])
      setCases(Array.isArray(caseData?.items) ? caseData.items : [])
      setLeaves(Array.isArray(leaveRows) ? leaveRows : [])
      setBalance(bal)
    } catch (err) {
      setCases([])
      setLeaves([])
      setBalance(null)
      setError(err.message || 'Could not load therapist leave context')
    } finally {
      setLoadingContext(false)
    }
  }, [therapistId, year])

  useEffect(() => {
    loadContext()
    setForm(EMPTY_FORM)
  }, [loadContext])

  const assignedCases = useMemo(
    () =>
      cases.map((c) => ({
        id: c.id,
        child_name: c.child_name,
        case_code: c.case_code,
        product_module: c.product_module,
        service_type: c.service_type,
        status: c.status,
      })),
    [cases],
  )

  function selectTherapist(therapist) {
    setTherapistId(String(therapist.id))
    setSelectedTherapistSnapshot(therapist)
    setSuccess('')
    setError('')
  }

  function clearTherapist() {
    setTherapistId('')
    setSelectedTherapistSnapshot(null)
    setTherapistSearch('')
    setTherapistResults([])
    setForm(EMPTY_FORM)
    setSuccess('')
    setError('')
  }

  async function submitManualLeave(e) {
    e.preventDefault()
    if (!therapistId) {
      setError('Select a therapist first.')
      return
    }
    if (assignedCases.length && !form.case_ids.length) {
      setError('Select at least one case, or use Select all.')
      return
    }
    if (!form.start_date || !form.end_date) {
      setError('Choose from and to dates.')
      return
    }
    if (form.end_date < form.start_date) {
      setError('End date must be on or after start date.')
      return
    }

    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const hasShadow = form.case_ids.some((id) => {
        const row = assignedCases.find((c) => Number(c.id) === Number(id))
        return row && caseServiceLine(row) === 'shadow_support'
      })
      const serviceLine = form.case_ids.length
        ? hasShadow
          ? assignedCases.some((c) => caseServiceLine(c) === 'homecare' && form.case_ids.includes(Number(c.id)))
            ? 'mixed'
            : 'shadow_support'
          : 'homecare'
        : 'shadow_support'

      await apiFetch('/api/v1/leave/manual', {
        method: 'POST',
        body: JSON.stringify({
          therapist_user_id: Number(therapistId),
          service_line: serviceLine,
          billing_category: form.billing_category,
          case_ids: form.case_ids.length ? form.case_ids.map(Number) : null,
          start_date: form.start_date,
          end_date: form.end_date,
          reason: form.reason || null,
          consulted_with_parents: form.consulted_with_parents,
        }),
      })

      setForm(EMPTY_FORM)
      setSuccess('Leave recorded and approved.')
      await loadContext()
      onLeaveRecorded?.()
    } catch (err) {
      setError(err.message || 'Could not record leave')
    } finally {
      setSubmitting(false)
    }
  }

  const yearOptions = [year - 1, year, year + 1]

  return (
    <div className="leave-mgmt-manual">
      <section className="leave-mgmt-manual__search-panel">
        <div className="leave-mgmt-manual__search-head">
          <label className="leave-mgmt-manual__year-field">
            <span>Balance year</span>
            <select
              className="admin-select"
              value={year}
              onChange={(e) => onYearChange?.(Number(e.target.value))}
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="leave-mgmt-manual__search-field">
          <span>Find therapist</span>
          <input
            type="search"
            className="admin-input leave-mgmt-manual__search-input"
            placeholder="Search by name or email…"
            value={therapistSearch}
            onChange={(e) => setTherapistSearch(e.target.value)}
            aria-label="Search therapists by name or email"
            autoComplete="off"
          />
        </label>

        {!searchReady ? (
          <p className="leave-mgmt-manual__results-empty">
            Type at least {MIN_SEARCH_LEN} characters to search by name or email.
          </p>
        ) : loadingTherapists ? (
          <p className="leave-mgmt-manual__results-empty">Searching…</p>
        ) : therapistResults.length === 0 ? (
          <p className="leave-mgmt-manual__results-empty">No therapists match that search.</p>
        ) : (
          <ul className="leave-mgmt-manual__results" role="listbox" aria-label="Therapist search results">
            {therapistResults.map((t) => {
              const isSelected = String(t.id) === String(therapistId)
              return (
                <li key={t.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    className={`leave-mgmt-manual__result${isSelected ? ' is-selected' : ''}`}
                    onClick={() => selectTherapist(t)}
                  >
                    <span className="leave-mgmt-manual__result-name">{t.full_name}</span>
                    <span className="leave-mgmt-manual__result-email">{t.email}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {!therapistId ? (
        <p className="admin-muted leave-mgmt-manual__hint">
          Search and select a therapist to view cases, leave history, and record leave manually.
        </p>
      ) : loadingContext ? (
        <div className="admin-skeleton" style={{ minHeight: 120 }} />
      ) : (
        <>
          <div className="leave-mgmt-manual__selected-bar">
            <p className="leave-mgmt-manual__selected-label">
              {selectedTherapist?.full_name || 'Therapist'}
              <span className="leave-mgmt-manual__selected-meta">
                {' '}
                · Leave credit {leaveCreditPendingLabel(balance)}
              </span>
            </p>
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={clearTherapist}>
              Change therapist
            </button>
          </div>

          <div className="leave-mgmt-manual__grid">
            <section className="leave-mgmt-manual__panel">
              <TherapistLeaveBalancePanel
                therapistUserId={Number(therapistId)}
                year={year}
                canEdit
                onSaved={loadContext}
              />
            </section>

            <section className="leave-mgmt-manual__panel">
              <h3 className="leave-mgmt-manual__panel-title">Active cases ({cases.length})</h3>
              {cases.length === 0 ? (
                <p className="admin-muted" style={{ margin: 0, fontSize: '0.875rem' }}>
                  No active assigned cases.
                </p>
              ) : (
                <ul className="leave-mgmt-manual__case-list">
                  {cases.map((c) => (
                    <li key={c.id}>{caseLabel(c)}</li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <section className="leave-mgmt-manual__panel leave-mgmt-manual__panel--wide">
            <h3 className="leave-mgmt-manual__panel-title">Leave history</h3>
            {leaves.length === 0 ? (
              <p className="admin-muted" style={{ margin: 0, fontSize: '0.875rem' }}>
                No leave records for this therapist yet.
              </p>
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table admin-table--compact">
                  <thead>
                    <tr>
                      <th>Split</th>
                      <th>Service</th>
                      <th>From</th>
                      <th>To</th>
                      <th>Days</th>
                      <th>Parents</th>
                      <th>Status</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaves.map((l) => (
                      <tr key={l.id}>
                        <td>{formatLeaveRecordSplit(l)}</td>
                        <td>{l.service_line || '—'}</td>
                        <td>{formatDisplayDate(l.start_date)}</td>
                        <td>{formatDisplayDate(l.end_date)}</td>
                        <td>{l.day_count ?? '—'}</td>
                        <td>{l.consulted_with_parents ? 'Yes' : '—'}</td>
                        <td>
                          <StatusBadge status={l.status} />
                        </td>
                        <td>{l.reason || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="leave-mgmt-manual__panel leave-mgmt-manual__panel--wide">
            <h3 className="leave-mgmt-manual__panel-title">Record leave manually</h3>
            <p className="admin-muted leave-mgmt-manual__hint">
              Entries are approved immediately — sessions may be cancelled and clients notified. Past dates are allowed.
            </p>
            {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
            {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}
            <form onSubmit={submitManualLeave} className="leave-mgmt-manual__form">
              <TherapistLeaveRequestFields
                assignedCases={assignedCases}
                caseIds={form.case_ids}
                onCaseIdsChange={(ids) => setForm((f) => ({ ...f, case_ids: ids }))}
                startDate={form.start_date}
                endDate={form.end_date}
                onStartDateChange={(v) => setForm((f) => ({ ...f, start_date: v }))}
                onEndDateChange={(v) => setForm((f) => ({ ...f, end_date: v }))}
                reason={form.reason}
                onReasonChange={(v) => setForm((f) => ({ ...f, reason: v }))}
                consultedWithParents={form.consulted_with_parents}
                onConsultedWithParentsChange={(v) => setForm((f) => ({ ...f, consulted_with_parents: v }))}
                billingCategory={form.billing_category}
                onBillingCategoryChange={(v) => setForm((f) => ({ ...f, billing_category: v }))}
                leaveBalance={balance}
                forTherapistUserId={Number(therapistId)}
                disabled={submitting}
              />
              <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting}>
                {submitting ? 'Saving…' : 'Record & approve leave'}
              </button>
            </form>
          </section>
        </>
      )}
    </div>
  )
}
