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
    <header className="vsl-stitch__context vsl-stitch__context--hero" aria-label="Session context">
      <div className="vsl-stitch__context-hero">
        <div>
          <h1 className="vsl-stitch__context-name">{childName || s?.child_name || 'Session log'}</h1>
          <div className="vsl-stitch__context-meta-row">
            {caseCode || s?.case_code ? (
              <span>Case {caseCode || s.case_code}</span>
            ) : null}
            {env ? <span>{env}</span> : null}
            {actual ? (
              <span>
                {actual}
                {duration ? ` · ${duration} min` : ''}
              </span>
            ) : null}
          </div>
        </div>
        <span className="vsl-stitch__badge vsl-stitch__badge--mint">Interpretation ready</span>
      </div>
      <details className="vsl-stitch__context-details">
        <summary>Session details</summary>
        <div className="vsl-stitch__context-row">
          <div>
            <span className="vsl-stitch__meta-label">Date</span>
            <strong>{s?.scheduled_date ? formatDisplayDate(s.scheduled_date) : '—'}</strong>
          </div>
          <div>
            <span className="vsl-stitch__meta-label">Therapist</span>
            <strong>{user?.full_name || user?.name || '—'}</strong>
          </div>
          <div>
            <span className="vsl-stitch__meta-label">Scheduled</span>
            <strong>{scheduled || '—'}</strong>
          </div>
          {serviceType ? (
            <div>
              <span className="vsl-stitch__meta-label">Service</span>
              <strong>{String(serviceType).replace(/_/g, ' ')}</strong>
            </div>
          ) : null}
        </div>
        {s?.actual_start_at ? (
          <button type="button" className="vsl-stitch__text-link" onClick={() => setTimesOpen(true)}>
            Edit session times
          </button>
        ) : null}
      </details>
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
