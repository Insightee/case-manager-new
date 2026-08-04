import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { mapCmMeetingToCalendarEvent } from '../../lib/googleCalendar.js'
import { BookingSuccessSheet } from '../shared/BookingSuccessSheet.jsx'
import { MeetingAvailabilitySlots } from './MeetingAvailabilitySlots.jsx'
import { MODAL_INPUT_STYLE, MODAL_LABEL_STYLE } from './meetingConstants.js'
import { buildMeetingsAvailabilityQuery, meetingDisplayTitle } from './meetingUtils.js'

export function RescheduleMeetingModal({ meeting, onClose, onRescheduled }) {
  const [form, setForm] = useState({
    scheduled_date: meeting.scheduled_date,
    scheduled_time: meeting.scheduled_time?.slice(0, 5) || '10:00',
    duration_minutes: meeting.duration_minutes || 30,
    reschedule_reason: '',
  })
  const [slots, setSlots] = useState(null)
  const [slotsLoading, setSlotsLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [successMeeting, setSuccessMeeting] = useState(null)

  function set(k, v) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  useEffect(() => {
    if (!form.scheduled_date) {
      setSlots(null)
      return
    }
    setSlotsLoading(true)
    const adminIds = meeting.admin_user_ids?.length
      ? meeting.admin_user_ids
      : (meeting.attendees || []).filter((a) => a.role === 'admin').map((a) => a.user_id)
    const qs = buildMeetingsAvailabilityQuery({
      targetDate: form.scheduled_date,
      durationMinutes: form.duration_minutes,
      caseManagerId: meeting.case_manager_user_id,
      therapistId: meeting.therapist_user_id,
      adminIds,
    })
    apiFetch(`/api/v1/meetings/availability?${qs}`)
      .then(setSlots)
      .catch(() => setSlots(null))
      .finally(() => setSlotsLoading(false))
  }, [
    form.scheduled_date,
    form.duration_minutes,
    meeting.case_manager_user_id,
    meeting.therapist_user_id,
    meeting.admin_user_ids,
    meeting.attendees,
  ])

  async function submit(e) {
    e.preventDefault()
    if (!form.scheduled_date || !form.scheduled_time) {
      setError('Pick a date and time slot.')
      return
    }
    if (!form.reschedule_reason.trim()) {
      setError('Share a short reason so attendees know why the time changed.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const result = await apiFetch(`/api/v1/meetings/${meeting.id}/reschedule`, {
        method: 'POST',
        body: JSON.stringify({
          scheduled_date: form.scheduled_date,
          scheduled_time: `${form.scheduled_time}:00`,
          duration_minutes: Number(form.duration_minutes) || 30,
          reschedule_reason: form.reschedule_reason.trim(),
        }),
      })
      setSuccessMeeting(result.new_meeting)
    } catch (err) {
      setError(err.message || 'Could not reschedule this meeting')
    } finally {
      setSaving(false)
    }
  }

  if (successMeeting) {
    return (
      <BookingSuccessSheet
        open
        title="Meeting rescheduled"
        event={mapCmMeetingToCalendarEvent(successMeeting)}
        onClose={() => {
          onRescheduled?.(successMeeting)
          setSuccessMeeting(null)
        }}
      />
    )
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 70, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(15,23,42,0.45)', padding: 16 }}>
      <div style={{ background: '#fff', borderRadius: 20, padding: 24, width: '100%', maxWidth: 540, maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 24px 64px rgba(0,0,0,0.18)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1e293b', margin: '0 0 8px' }}>Reschedule meeting</h2>
        <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '0 0 16px' }}>
          {meetingDisplayTitle(meeting) || meeting.child_name || 'Case manager meeting'}
        </p>
        {error ? (
          <p style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '8px 12px', fontSize: '0.8rem', color: '#991b1b', marginBottom: 12 }}>
            {error}
          </p>
        ) : null}
        <form onSubmit={submit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
            <label style={MODAL_LABEL_STYLE}>
              New date *
              <input
                type="date"
                style={MODAL_INPUT_STYLE}
                value={form.scheduled_date}
                required
                min={new Date().toISOString().slice(0, 10)}
                onChange={(e) => set('scheduled_date', e.target.value)}
              />
            </label>
            <label style={MODAL_LABEL_STYLE}>
              Duration
              <select style={MODAL_INPUT_STYLE} value={form.duration_minutes} onChange={(e) => set('duration_minutes', e.target.value)}>
                {[30, 45, 60, 90].map((d) => (
                  <option key={d} value={d}>{d} min</option>
                ))}
              </select>
            </label>
          </div>

          <MeetingAvailabilitySlots
            slots={slots}
            loading={slotsLoading}
            selectedTime={form.scheduled_time}
            targetDate={form.scheduled_date}
            label="Open slots for attendees"
            onSelectTime={(time) => set('scheduled_time', time)}
            onSelectDate={(date) => set('scheduled_date', date)}
          />

          <label style={MODAL_LABEL_STYLE}>
            Reason for reschedule *
            <textarea
              style={{ ...MODAL_INPUT_STYLE, minHeight: 72, resize: 'vertical', fontFamily: 'inherit' }}
              placeholder="e.g. Parent requested a later time"
              value={form.reschedule_reason}
              onChange={(e) => set('reschedule_reason', e.target.value)}
              required
            />
          </label>

          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button
              type="submit"
              disabled={saving}
              style={{ flex: 1, background: '#4f46e5', color: '#fff', border: 'none', borderRadius: 12, padding: '12px 0', fontWeight: 700, fontSize: '0.9rem', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}
            >
              {saving ? 'Saving…' : 'Confirm reschedule'}
            </button>
            <button type="button" style={{ background: '#f1f5f9', border: 'none', borderRadius: 12, padding: '12px 16px', fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }} onClick={onClose}>
              Close
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
