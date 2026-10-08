/** @typedef {{ session_logs: boolean, therapist_leave: boolean, appointments: boolean, billing: boolean, reports: boolean, meetings: boolean, incidents: boolean }} ParentEmailPreferences */

export const DEFAULT_PARENT_EMAIL_PREFERENCES = {
  session_logs: true,
  therapist_leave: true,
  appointments: true,
  billing: true,
  reports: true,
  meetings: true,
  incidents: true,
}

/** @type {Array<{ key: keyof ParentEmailPreferences, label: string, description: string, examples: string }>} */
export const PARENT_EMAIL_PREFERENCE_OPTIONS = [
  {
    key: 'appointments',
    label: 'Same-day cancellations & changes',
    description: 'When a session today is cancelled or moved by your care team.',
    examples: 'e.g. “Today’s session cancelled”',
  },
  {
    key: 'session_logs',
    label: 'Session logs',
    description: 'When your therapist submits a session log.',
    examples: 'e.g. “Session log submitted”',
  },
  {
    key: 'reports',
    label: 'Monthly reports',
    description: 'When a monthly report is published to your portal.',
    examples: 'e.g. “Monthly report ready”',
  },
  {
    key: 'incidents',
    label: 'Incidents & safety',
    description: 'When your case manager shares an important safety update or escalates your support request.',
    examples: 'e.g. care-team update, escalated support ticket',
  },
  {
    key: 'billing',
    label: 'Invoices & payments',
    description: 'When a new invoice is ready or a payment reminder is sent.',
    examples: 'e.g. “Invoice ready”, payment reminders',
  },
  {
    key: 'meetings',
    label: 'Care-team meetings',
    description: 'Meeting invites and cancellations from your care team (includes calendar attachments).',
    examples: 'e.g. meeting invite or cancellation',
  },
]

/**
 * @param {unknown} raw
 * @param {boolean | undefined} legacyLogLeaveEmails
 * @returns {ParentEmailPreferences}
 */
export function emailPreferencesFromApi(raw, legacyLogLeaveEmails) {
  if (raw && typeof raw === 'object' && ('session_logs' in raw || 'appointments' in raw)) {
    const src = raw
    return {
      session_logs: src.session_logs !== false,
      therapist_leave: src.therapist_leave !== false,
      appointments: src.appointments !== false,
      billing: src.billing !== false,
      reports: src.reports !== false,
      meetings: src.meetings !== false,
      incidents: src.incidents !== false,
    }
  }
  if (legacyLogLeaveEmails === false) {
    return {
      ...DEFAULT_PARENT_EMAIL_PREFERENCES,
      session_logs: false,
      therapist_leave: false,
    }
  }
  return { ...DEFAULT_PARENT_EMAIL_PREFERENCES }
}

/**
 * @param {ParentEmailPreferences} prefs
 */
export function countEnabledEmailPreferences(prefs) {
  return PARENT_EMAIL_PREFERENCE_OPTIONS.filter((opt) => prefs[opt.key]).length
}
