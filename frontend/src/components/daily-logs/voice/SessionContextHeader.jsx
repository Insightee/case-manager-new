import { useState } from 'react'
import { useAuth } from '../../../context/AuthContext.jsx'
import { formatDisplayDate } from '../../../lib/datetime.js'
import {
  effectiveDurationMins,
  formatClockRange,
  formatEditedRange,
  formatScheduledRange,
} from '../../../lib/sessionTimes.js'
import { EditActualTimesModal } from '../EditActualTimesModal.jsx'

const ENVIRONMENT_LABELS = {
  home: 'Home',
  school: 'School',
  clinic: 'Clinic',
  community: 'Community',
  online: 'Online',
}

function environmentLabel(structuredSession, session) {
  const env = structuredSession?.session_context?.environment
  if (env) return ENVIRONMENT_LABELS[env] || env
  return session?.mode ? String(session.mode).toLowerCase().replace(/^\w/, (c) => c.toUpperCase()) : null
}

/**
 * Session context header — always visible on draft/preview.
 * Times edits go through the audited actual-times modal (reason + clock record kept).
 */
export function SessionContextHeader({ session, caseCode, childName, structuredSession, onTimesSaved }) {
  const { user } = useAuth()
  const [timesOpen, setTimesOpen] = useState(false)
  const [liveSession, setLiveSession] = useState(session)

  const s = liveSession || session
  const scheduled = formatScheduledRange(s)
  const edited = formatEditedRange(s, { suffix: '' })
  const actual = edited || formatClockRange(s, { suffix: '' })
  const duration = effectiveDurationMins(s, null)
  const env = environmentLabel(structuredSession, s)
  const serviceType = s?.product_module || s?.service_type || null

  return (
    <header className="vsl-stitch__context" aria-label="Session context">
      <div className="vsl-stitch__context-row">
        <div>
          <span className="vsl-stitch__meta-label">Client</span>
          <strong>{childName || s?.child_name || '—'}</strong>
        </div>
        <div>
          <span className="vsl-stitch__meta-label">Case</span>
          <strong>{caseCode || s?.case_code || '—'}</strong>
        </div>
        <div>
          <span className="vsl-stitch__meta-label">Date</span>
          <strong>{s?.scheduled_date ? formatDisplayDate(s.scheduled_date) : '—'}</strong>
        </div>
        <div>
          <span className="vsl-stitch__meta-label">Therapist</span>
          <strong>{user?.full_name || user?.name || '—'}</strong>
        </div>
      </div>
      <div className="vsl-stitch__context-row">
        <div>
          <span className="vsl-stitch__meta-label">Scheduled</span>
          <strong>{scheduled || '—'}</strong>
        </div>
        <div>
          <span className="vsl-stitch__meta-label">Actual</span>
          <strong>
            {actual || '—'}
            {duration ? ` · ${duration} min` : ''}
            {s?.actual_times_edited || edited ? ' (edited)' : ''}
          </strong>
        </div>
        {env ? (
          <div>
            <span className="vsl-stitch__meta-label">Environment</span>
            <strong>{env}</strong>
          </div>
        ) : null}
        {serviceType ? (
          <div>
            <span className="vsl-stitch__meta-label">Service</span>
            <strong>{String(serviceType).replace(/_/g, ' ')}</strong>
          </div>
        ) : null}
      </div>
      {s?.actual_start_at ? (
        <button
          type="button"
          className="vsl-stitch__btn vsl-stitch__btn--ghost vsl-stitch__context-edit"
          onClick={() => setTimesOpen(true)}
        >
          Edit session times
        </button>
      ) : null}
      <EditActualTimesModal
        open={timesOpen}
        session={s}
        onClose={() => setTimesOpen(false)}
        onSaved={(updated) => {
          setLiveSession((prev) => ({ ...(prev || session), ...updated }))
          onTimesSaved?.(updated)
        }}
      />
    </header>
  )
}
