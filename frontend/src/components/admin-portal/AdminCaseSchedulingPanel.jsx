import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { TherapistCalendar } from '../scheduling/TherapistCalendar.jsx'
import { SlotDetailSheet } from '../scheduling/SlotDetailSheet.jsx'
import { AdminScheduleSessionModal } from './AdminScheduleSessionModal.jsx'
import { AdminAssignSchedulePanel } from './AdminAssignSchedulePage.jsx'

function ShadowBlockSection({ caseItem, assignments, onDone }) {
  const [therapistId, setTherapistId] = useState(
    assignments?.[0]?.therapist_user_id ? String(assignments[0].therapist_user_id) : '',
  )
  const [dates, setDates] = useState('')
  const [startTime, setStartTime] = useState('08:00')
  const [durationHours, setDurationHours] = useState(8)
  const [conflicts, setConflicts] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  function parsedDates() {
    return dates
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter((s) => /^\d{4}-\d{2}-\d{2}$/.test(s))
  }

  async function preview() {
    setError('')
    setConflicts(null)
    const ds = parsedDates()
    if (!ds.length || !therapistId) {
      setError('Enter therapist and at least one date (YYYY-MM-DD).')
      return
    }
    try {
      const qs = new URLSearchParams({
        therapist_user_id: therapistId,
        start_time: startTime,
        duration_hours: durationHours,
      })
      ds.forEach((d) => qs.append('dates', d))
      const res = await apiFetch(`/api/v1/scheduling/shadow-block/preview?${qs}`)
      setConflicts(res.conflicts || [])
    } catch (err) {
      setError(err.message || 'Preview failed')
    }
  }

  async function schedule() {
    setError('')
    setSuccess('')
    setSaving(true)
    const ds = parsedDates()
    if (!ds.length || !therapistId) {
      setError('Enter therapist and at least one date.')
      setSaving(false)
      return
    }
    try {
      const res = await apiFetch('/api/v1/scheduling/shadow-block', {
        method: 'POST',
        body: JSON.stringify({
          case_id: caseItem.id,
          therapist_user_id: Number(therapistId),
          dates: ds,
          start_time: startTime,
          duration_hours: Number(durationHours),
        }),
      })
      setSuccess(`${res.created?.length || 0} block(s) scheduled.`)
      setDates('')
      setConflicts(null)
      onDone?.()
    } catch (err) {
      const detail = err?.detail
      if (detail?.conflicts) {
        setConflicts(detail.conflicts)
        setError('Conflicts detected — resolve them or remove conflicting dates.')
      } else {
        setError(err.message || 'Schedule failed')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="admin-panel" style={{ padding: 20, marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>Shadow care blocks</h3>
      <p style={{ fontSize: '0.8rem', color: '#6b7280', marginBottom: 16 }}>
        Bulk-assign full-day blocks for this shadow support case.
      </p>
      {error ? <p style={{ color: '#b91c1c', fontSize: '0.85rem' }}>{error}</p> : null}
      {success ? <p style={{ color: '#059669', fontSize: '0.85rem' }}>{success}</p> : null}
      <div style={{ display: 'grid', gap: 12 }}>
        <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>
          Therapist
          <select
            className="admin-input"
            style={{ display: 'block', marginTop: 4, width: '100%' }}
            value={therapistId}
            onChange={(e) => setTherapistId(e.target.value)}
          >
            <option value="">— select —</option>
            {assignments.map((a) => (
              <option key={a.therapist_user_id} value={a.therapist_user_id}>
                {a.therapist_name || `Therapist #${a.therapist_user_id}`}
              </option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: '0.85rem', fontWeight: 600 }}>
          Dates (comma or space separated)
          <textarea
            className="admin-input"
            rows={3}
            style={{ display: 'block', marginTop: 4, width: '100%', fontFamily: 'monospace' }}
            value={dates}
            onChange={(e) => setDates(e.target.value)}
          />
        </label>
        <div style={{ display: 'flex', gap: 10 }}>
          <button type="button" className="admin-btn" onClick={preview}>
            Preview conflicts
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--primary"
            disabled={saving || (conflicts !== null && conflicts.length > 0)}
            onClick={schedule}
          >
            {saving ? 'Scheduling…' : 'Schedule blocks'}
          </button>
        </div>
      </div>
    </div>
  )
}

const MODES = [
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'calendar', label: 'Calendar' },
  { id: 'book', label: 'Book session' },
  { id: 'recurring', label: 'Recurring assign' },
  { id: 'shadow', label: 'Shadow blocks' },
]

export function AdminCaseSchedulingPanel({ caseItem, assignments, onDone, isShadow }) {
  const [searchParams] = useSearchParams()
  const slotIdParam = searchParams.get('slotId')
  const activeAssignment = assignments?.find((a) => a.status === 'ACTIVE') || assignments?.[0]
  const therapistUserId = activeAssignment?.therapist_user_id

  const [mode, setMode] = useState(() => (slotIdParam ? 'calendar' : 'upcoming'))
  const [upcoming, setUpcoming] = useState([])
  const [loading, setLoading] = useState(true)
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [detailSlot, setDetailSlot] = useState(null)
  const [calendarRefresh, setCalendarRefresh] = useState(0)

  useEffect(() => {
    if (!caseItem?.id) return
    setLoading(true)
    apiFetch(`/api/v1/sessions?case_id=${caseItem.id}&page_size=50`)
      .then((d) => {
        const rows = unwrapList(d)
        const now = new Date()
        setUpcoming(
          rows
            .filter((s) => s.scheduled_at && new Date(s.scheduled_at) >= now)
            .sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at))
            .slice(0, 20),
        )
      })
      .catch(() => setUpcoming([]))
      .finally(() => setLoading(false))
  }, [caseItem?.id, onDone])

  const visibleModes = useMemo(
    () =>
      MODES.filter((m) => {
        if (m.id === 'shadow' && !isShadow) return false
        if (m.id === 'calendar' && !therapistUserId) return false
        return true
      }),
    [isShadow, therapistUserId],
  )

  useEffect(() => {
    if (!slotIdParam || mode !== 'calendar') return
    const from = new Date().toISOString().slice(0, 10)
    const toDate = new Date()
    toDate.setDate(toDate.getDate() + 60)
    const to = toDate.toISOString().slice(0, 10)
    const tid = therapistUserId ? `&therapist_id=${therapistUserId}` : ''
    const cid = caseItem?.id ? `&case_id=${caseItem.id}` : ''
    apiFetch(`/api/v1/scheduling/calendar?from_date=${from}&to_date=${to}${tid}${cid}`)
      .then((cal) => {
        const slot = (cal?.slots || []).find((s) => String(s.id) === String(slotIdParam))
        if (slot) setDetailSlot(slot)
      })
      .catch(() => {})
  }, [slotIdParam, mode, therapistUserId, caseItem?.id])

  return (
    <section>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        {visibleModes.map((m) => (
          <button
            key={m.id}
            type="button"
            className={`admin-btn admin-btn--sm ${mode === m.id ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => setMode(m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {mode === 'upcoming' && (
        <div className="admin-panel" style={{ padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>Upcoming sessions</h3>
          {loading ? (
            <p className="admin-muted">Loading…</p>
          ) : upcoming.length === 0 ? (
            <p className="admin-muted">No upcoming sessions for this case.</p>
          ) : (
            <ul className="admin-queue">
              {upcoming.map((s) => (
                <li key={s.id} className="admin-queue__item">
                  <div>
                    <p className="admin-queue__title">
                      {s.scheduled_at ? new Date(s.scheduled_at).toLocaleString() : 'Session'}
                    </p>
                    <p className="admin-queue__meta">{s.status}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {mode === 'calendar' && therapistUserId ? (
        <div className="admin-panel" style={{ padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>Case calendar</h3>
          <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: 12 }}>
            Same week view as therapist and parent portals. Pending reschedules show with ⏳ — tap to confirm or
            decline.
          </p>
          <TherapistCalendar
            therapistId={therapistUserId}
            caseId={caseItem?.id}
            mode="therapist"
            refreshKey={calendarRefresh}
            showLeaveActions={false}
            onSlotClick={(slot) => setDetailSlot(slot)}
            selectedSlotId={detailSlot?.id}
          />
          <SlotDetailSheet
            open={!!detailSlot}
            slot={detailSlot}
            onClose={() => setDetailSlot(null)}
            onChanged={() => {
              setDetailSlot(null)
              setCalendarRefresh((k) => k + 1)
              onDone?.()
            }}
          />
        </div>
      ) : null}

      {mode === 'book' && (
        <div className="admin-panel" style={{ padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>Book a session</h3>
          <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: 12 }}>
            Pick an available slot and book for this case.
          </p>
          <button type="button" className="admin-btn admin-btn--primary" onClick={() => setScheduleOpen(true)}>
            Schedule session
          </button>
        </div>
      )}

      {mode === 'recurring' && (
        <AdminAssignSchedulePanel caseItem={caseItem} assignments={assignments} onDone={onDone} />
      )}

      {mode === 'shadow' && isShadow && (
        <ShadowBlockSection caseItem={caseItem} assignments={assignments} onDone={onDone} />
      )}

      <AdminScheduleSessionModal
        open={scheduleOpen}
        caseItem={caseItem}
        onClose={() => setScheduleOpen(false)}
        onDone={() => {
          setScheduleOpen(false)
          onDone?.()
        }}
      />
    </section>
  )
}
