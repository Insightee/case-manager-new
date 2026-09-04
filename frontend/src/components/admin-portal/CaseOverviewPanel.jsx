import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateTime } from '../../lib/datetime.js'
import { displayCaseClientName } from '../../lib/adminCasePipeline.js'
import { CaseClientStatusCard } from './CaseClientStatusCard.jsx'
import { CaseServiceAddressForm } from './CaseServiceAddressForm.jsx'
import { CaseZohoIdForm } from './CaseZohoIdForm.jsx'
import { StatusBadge } from './ui/index.js'

function formatMeetingType(type) {
  if (!type) return 'Meeting'
  return String(type)
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function contactHref(kind, value) {
  if (!value) return null
  if (kind === 'phone') return `tel:${String(value).replace(/\s+/g, '')}`
  return `mailto:${value}`
}

function contactBlock(contact) {
  if (!contact) {
    return <p className="admin-muted" style={{ margin: 0 }}>Unlinked</p>
  }

  return (
    <div className="admin-case-overview__contact">
      <p className="admin-case-overview__contact-name">{displayCaseClientName(contact.name) || 'Unlinked'}</p>
      <p className="admin-case-overview__contact-links">
        {contact.phone ? (
          <a href={contactHref('phone', contact.phone)} className="admin-case-overview__contact-link">
            {contact.phone}
          </a>
        ) : (
          <span>Phone not set</span>
        )}
        {contact.email ? (
          <a href={contactHref('email', contact.email)} className="admin-case-overview__contact-link">
            {contact.email}
          </a>
        ) : (
          <span>Email not set</span>
        )}
      </p>
    </div>
  )
}

export function CaseOverviewPanel({ caseRow, canEditCase, canReopenCase, onCaseChanged }) {
  const [notes, setNotes] = useState(caseRow?.notes || '')
  const [notesSaving, setNotesSaving] = useState(false)
  const [notesError, setNotesError] = useState('')
  const [recentMeetings, setRecentMeetings] = useState([])
  const [meetingsLoading, setMeetingsLoading] = useState(true)

  const isMentor = Boolean(caseRow?.access_as_mentor)
  const canEditNotes = Boolean(canEditCase && !isMentor)
  const canEditAddress = Boolean(canEditCase && !isMentor)

  useEffect(() => {
    setNotes(caseRow?.notes || '')
    setNotesError('')
  }, [caseRow?.id, caseRow?.notes])

  useEffect(() => {
    if (!caseRow?.id) return
    let cancelled = false
    setMeetingsLoading(true)
    apiFetch(`/api/v1/meetings?case_id=${caseRow.id}`)
      .then((rows) => {
        if (!cancelled) setRecentMeetings((rows || []).slice(0, 5))
      })
      .catch(() => {
        if (!cancelled) setRecentMeetings([])
      })
      .finally(() => {
        if (!cancelled) setMeetingsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [caseRow?.id])

  const serviceAddressText = useMemo(() => {
    const addr = caseRow?.service_address
    if (!addr) return null
    return [addr.address_line1, addr.address_line2, addr.city, addr.state, addr.pincode]
      .filter(Boolean)
      .join(', ')
  }, [caseRow?.service_address])

  async function saveNotes(event) {
    event.preventDefault()
    if (!canEditNotes) return
    setNotesSaving(true)
    setNotesError('')
    try {
      const updated = await apiFetch(`/api/v1/cases/${caseRow.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ notes: notes.trim() || null }),
      })
      onCaseChanged?.(updated)
    } catch (err) {
      setNotesError(err.message || 'Looks like we still need a few details before we can save this.')
    } finally {
      setNotesSaving(false)
    }
  }

  return (
    <section className="admin-case-overview" aria-labelledby="admin-case-overview-title">
      <h2 id="admin-case-overview-title" className="visually-hidden">
        Case overview
      </h2>

      <div className="admin-panel admin-case-overview__panel">
        <div className="admin-case-overview__panel-head">
          <div>
            <p className="admin-case-overview__eyebrow">People &amp; contact</p>
            <h3 className="admin-case-overview__title">Parent and therapist</h3>
          </div>
        </div>
        <div className="admin-case-overview__contacts">
          <div className="admin-case-overview__contact-card">
            <p className="admin-case-overview__contact-label">Parent</p>
            {contactBlock(caseRow?.parent_contact)}
          </div>
          <div className="admin-case-overview__contact-card">
            <p className="admin-case-overview__contact-label">Therapist</p>
            {contactBlock(caseRow?.therapist_contact)}
          </div>
        </div>
      </div>

      <div className="admin-panel admin-case-overview__panel">
        <div className="admin-case-overview__panel-head">
          <div>
            <p className="admin-case-overview__eyebrow">Service location</p>
            <h3 className="admin-case-overview__title">Address and maps</h3>
          </div>
        </div>
        {canEditAddress ? (
          <CaseServiceAddressForm caseItem={caseRow} onSave={async (payload) => {
            const updated = await apiFetch(`/api/v1/cases/${caseRow.id}`, {
              method: 'PATCH',
              body: JSON.stringify(payload),
            })
            onCaseChanged?.(updated)
          }} />
        ) : (
          <div className="admin-case-overview__readonly">
            <p className="admin-case-overview__readonly-text">{serviceAddressText || 'Service address not set.'}</p>
            {caseRow?.maps_url ? (
              <a
                href={caseRow.maps_url}
                target="_blank"
                rel="noreferrer"
                className="admin-btn admin-btn--ghost admin-btn--sm"
              >
                Open in Maps
              </a>
            ) : null}
          </div>
        )}
      </div>

      <div className="admin-panel admin-case-overview__panel">
        <div className="admin-case-overview__panel-head">
          <div>
            <p className="admin-case-overview__eyebrow">Case notes</p>
            <h3 className="admin-case-overview__title">Internal note</h3>
          </div>
        </div>
        {canEditNotes ? (
          <form onSubmit={saveNotes} className="admin-case-overview__notes-form">
            <label className="admin-label" htmlFor={`case-notes-${caseRow.id}`}>
              Notes
              <textarea
                id={`case-notes-${caseRow.id}`}
                className="admin-input"
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add a quick operational note."
              />
            </label>
            {notesError ? <p className="admin-alert admin-alert--error">{notesError}</p> : null}
            <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={notesSaving}>
              {notesSaving ? 'Saving…' : 'Save notes'}
            </button>
          </form>
        ) : (
          <div className="admin-case-overview__readonly">
            <p className="admin-case-overview__readonly-text">{caseRow?.notes || 'No case notes yet.'}</p>
          </div>
        )}
      </div>

      <CaseClientStatusCard
        caseId={caseRow.id}
        caseRow={caseRow}
        canEdit={Boolean(canEditCase && !isMentor)}
        canReopen={canReopenCase}
        onStatusChanged={onCaseChanged}
      />

      <div className="admin-panel admin-case-overview__panel">
        <div className="admin-case-overview__panel-head">
          <div>
            <p className="admin-case-overview__eyebrow">Ops meta</p>
            <h3 className="admin-case-overview__title">Zoho and case metadata</h3>
          </div>
        </div>
        <div className="admin-case-overview__meta">
          <div className="admin-case-overview__meta-item">
            <span className="admin-case-overview__meta-label">Case code</span>
            <span className="admin-case-overview__meta-value">{caseRow.case_code}</span>
          </div>
          <div className="admin-case-overview__meta-item">
            <span className="admin-case-overview__meta-label">Region</span>
            <span className="admin-case-overview__meta-value">{caseRow.region || '—'}</span>
          </div>
          <div className="admin-case-overview__meta-item">
            <span className="admin-case-overview__meta-label">Stage</span>
            <span className="admin-case-overview__meta-value">{caseRow.operational_stage || '—'}</span>
          </div>
          <div className="admin-case-overview__meta-item">
            <span className="admin-case-overview__meta-label">Created</span>
            <span className="admin-case-overview__meta-value">
              {caseRow.created_at ? new Date(caseRow.created_at).toLocaleDateString() : '—'}
            </span>
          </div>
        </div>
        <div className="admin-case-overview__zoho">
          {canEditAddress || canEditCase ? (
            <CaseZohoIdForm caseItem={caseRow} canEdit={canEditCase} onSaved={onCaseChanged} />
          ) : (
            <p className="admin-case-overview__readonly-text">
              Zoho ID: {caseRow.zoho_id || 'Not set'}
            </p>
          )}
        </div>
      </div>

      <div className="admin-panel admin-case-overview__panel">
        <div className="admin-case-overview__panel-head admin-case-overview__panel-head--split">
          <div>
            <p className="admin-case-overview__eyebrow">Recent meetings</p>
            <h3 className="admin-case-overview__title">Last 5 meetings</h3>
          </div>
          <Link to={`/admin/meetings?case_id=${caseRow.id}`} className="admin-btn admin-btn--ghost admin-btn--sm">
            Open meetings
          </Link>
        </div>
        {meetingsLoading ? (
          <p className="admin-muted">Loading recent meetings…</p>
        ) : recentMeetings.length ? (
          <ul className="admin-case-overview__meeting-list">
            {recentMeetings.map((meeting) => (
              <li key={meeting.id} className="admin-case-overview__meeting-item">
                <div className="admin-case-overview__meeting-main">
                  <div className="admin-case-overview__meeting-head">
                    <strong>{meeting.title || formatMeetingType(meeting.meeting_type)}</strong>
                    <StatusBadge status={meeting.display_status || meeting.status} />
                  </div>
                  <p className="admin-case-overview__meeting-meta">
                    {formatDisplayDateTime(meeting.scheduled_date, meeting.scheduled_time) || meeting.scheduled_date}
                    {' · '}
                    {formatMeetingType(meeting.meeting_type)}
                  </p>
                  <p className="admin-case-overview__meeting-text">
                    <span className="admin-case-overview__meeting-label">Outcome:</span>{' '}
                    {meeting.notes_outcome || '—'}
                  </p>
                  <p className="admin-case-overview__meeting-text">
                    <span className="admin-case-overview__meeting-label">Summary:</span>{' '}
                    {meeting.notes_summary || '—'}
                  </p>
                </div>
                <Link to="/admin/meetings" className="admin-case-overview__meeting-link">
                  Open →
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="admin-empty">No meetings yet.</p>
        )}
      </div>
    </section>
  )
}
