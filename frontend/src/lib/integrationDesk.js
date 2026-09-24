/** Super-admin integration desk: scopes, token life, and webhook events. */

export const INFO_ACCESS = [
  {
    id: 'cases',
    label: 'Cases',
    hint: 'Strengths, support needs, environment, and participation patterns.',
    readScope: 'cases:read',
    writeScope: 'cases:write',
  },
  {
    id: 'sessions',
    label: 'Sessions',
    hint: 'Progress signals and strategy effectiveness from session logs.',
    readScope: 'sessions:summarize',
    writeScope: 'sessions:write',
  },
  {
    id: 'reports',
    label: 'Reports',
    hint: 'Observation, monthly, and progress summaries. Stays read-only so a key cannot mark a report complete.',
    readScope: 'reports:read',
    writeScope: null,
  },
  {
    id: 'goals',
    label: 'Goals & strategies',
    hint: 'Library goal and strategy identifiers, status, and short labels.',
    readScope: 'goals:read',
    writeScope: 'goals:write',
  },
  {
    id: 'iep',
    label: 'IEP framework',
    hint: 'Goal, strategy, and measurement framework identifiers. Stays read-only.',
    readScope: 'iep:read',
    writeScope: null,
  },
  {
    id: 'reporting',
    label: 'Pending reporting',
    hint: 'Overdue and missing monthly items for granted cases.',
    readScope: 'reporting:pending',
    writeScope: null,
  },
  {
    id: 'ops',
    label: 'Operations',
    hint: 'Anonymised counts only. No names or case identifiers.',
    readScope: 'ops:summary',
    writeScope: null,
  },
  {
    id: 'profiles',
    label: 'Therapist profiles',
    hint: 'Listing name, bio, qualifications, certificates, and services. Write creates a profile for an existing therapist.',
    readScope: 'profiles:read',
    writeScope: 'profiles:write',
  },
]

export const KEY_TTL_OPTIONS = [
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
  { value: 365, label: '1 year' },
  { value: 0, label: 'No expiry' },
]

export const ACCESS_TOKEN_OPTIONS = [
  { value: 15, label: '15 min' },
  { value: 60, label: '1 hour' },
  { value: 480, label: '8 hours' },
  { value: 1440, label: '24 hours' },
]

export const WEBHOOK_EVENTS = [
  { id: 'case.updated', label: 'Case updated', hint: 'Structured case fields changed.' },
  { id: 'session.logged', label: 'Session logged', hint: 'A session log was saved.' },
  { id: 'report.draft_ready', label: 'Report draft ready', hint: 'A draft is ready for review. Never a completed report.' },
  { id: 'goal.pending_review', label: 'Goal pending review', hint: 'A therapist goal is waiting for case manager review.' },
  { id: 'iep.updated', label: 'IEP updated', hint: 'IEP framework identifiers changed.' },
  { id: 'reporting.overdue', label: 'Reporting overdue', hint: 'A monthly item is past due.' },
  { id: 'incident.reported', label: 'Incident reported', hint: 'An incident was filed on a granted case.' },
]

const INFO_BY_ID = Object.fromEntries(INFO_ACCESS.map((item) => [item.id, item]))

export function emptyKeyDraft() {
  return {
    name: '',
    allowRead: true,
    allowWrite: false,
    infoAccess: ['cases', 'sessions', 'reports'],
    accessTokenMinutes: 15,
    keyTtlDays: 90,
    mcpEnabled: true,
    caseIdsText: '',
    rateLimit: 60,
  }
}

export function emptyWebhookDraft() {
  return {
    integrationClientId: '',
    url: '',
    events: ['session.logged', 'report.draft_ready'],
    status: 'active',
  }
}

export function parseCaseIds(text) {
  const raw = String(text || '').trim()
  if (!raw) return { ids: [], error: '' }
  const parts = raw.split(/[\s,]+/).filter(Boolean)
  const ids = []
  for (const part of parts) {
    if (!/^\d+$/.test(part)) {
      return { ids: [], error: 'Case IDs need to be numbers, separated by commas.' }
    }
    ids.push(Number(part))
  }
  return { ids: [...new Set(ids)], error: '' }
}

export function scopesFromDraft(draft) {
  const scopes = []
  for (const item of INFO_ACCESS) {
    if (!draft.infoAccess?.includes(item.id)) continue
    if (draft.allowRead && item.readScope) scopes.push(item.readScope)
    if (draft.allowWrite && item.writeScope) scopes.push(item.writeScope)
  }
  return scopes
}

export function validateKeyDraft(draft) {
  const name = String(draft.name || '').trim()
  if (!name) return 'Add a name so you can tell this key apart later.'
  if (name.length > 128) return 'Keep the name under 128 characters.'
  if (!draft.allowRead && !draft.allowWrite) return 'Turn on Read or Write before saving this key.'
  if (!draft.infoAccess?.length) return 'Choose at least one kind of information this key can use.'
  const scopes = scopesFromDraft(draft)
  if (!scopes.length) {
    return 'Those areas stay read-only. Turn Read on, or choose Cases, Sessions, Goals, or Therapist profiles while Write is on.'
  }
  const cases = parseCaseIds(draft.caseIdsText)
  if (cases.error) return cases.error
  if (![15, 60, 480, 1440].includes(Number(draft.accessTokenMinutes))) {
    return 'Choose how long each access token stays valid.'
  }
  if (![0, 30, 90, 365].includes(Number(draft.keyTtlDays))) {
    return 'Choose how long this API key stays valid.'
  }
  return ''
}

export function keyDraftFromClient(client) {
  const infoAccess = Array.isArray(client?.info_access) ? client.info_access : []
  return {
    name: client?.name || '',
    allowRead: Boolean(client?.allow_read),
    allowWrite: Boolean(client?.allow_write),
    infoAccess: infoAccess.length ? [...infoAccess] : INFO_ACCESS.filter((item) =>
      (client?.scopes || []).includes(item.readScope) || (item.writeScope && (client?.scopes || []).includes(item.writeScope)),
    ).map((item) => item.id),
    accessTokenMinutes: Number(client?.access_token_minutes) || 15,
    keyTtlDays: client?.key_ttl_days == null ? 365 : Number(client.key_ttl_days),
    mcpEnabled: client?.mcp_enabled !== false,
    caseIdsText: (client?.case_ids || []).join(', '),
    rateLimit: Number(client?.rate_limit_per_minute) || 60,
  }
}

export function keyPayloadFromDraft(draft) {
  const cases = parseCaseIds(draft.caseIdsText)
  return {
    name: String(draft.name || '').trim(),
    allow_read: Boolean(draft.allowRead),
    allow_write: Boolean(draft.allowWrite),
    info_access: [...(draft.infoAccess || [])],
    access_token_minutes: Number(draft.accessTokenMinutes),
    key_ttl_days: Number(draft.keyTtlDays),
    mcp_enabled: Boolean(draft.mcpEnabled),
    case_ids: cases.ids,
    rate_limit_per_minute: Number(draft.rateLimit) || 60,
  }
}

export function validateWebhookDraft(draft) {
  if (!draft.integrationClientId) return 'Choose which API key this webhook belongs to.'
  const url = String(draft.url || '').trim()
  if (!url) return 'Add an https address so this webhook has somewhere to send events.'
  if (!/^https:\/\/.+/i.test(url)) return 'Webhook addresses need to start with https://.'
  if (url.length > 512) return 'That webhook address is too long to store.'
  if (!draft.events?.length) return 'Choose at least one event to send.'
  const known = new Set(WEBHOOK_EVENTS.map((event) => event.id))
  if (draft.events.some((event) => !known.has(event))) return 'One of those events is not available.'
  return ''
}

export function infoLabel(id) {
  return INFO_BY_ID[id]?.label || id
}

export function keyTtlLabel(days) {
  const match = KEY_TTL_OPTIONS.find((option) => option.value === Number(days))
  return match?.label || `${days} days`
}

export function accessTokenLabel(minutes) {
  const match = ACCESS_TOKEN_OPTIONS.find((option) => option.value === Number(minutes))
  return match?.label || `${minutes} min`
}

export function integrationApiOrigin() {
  const env = typeof import.meta !== 'undefined' ? import.meta.env : undefined
  const configured = String(env?.VITE_API_URL || '').replace(/\/$/, '')
  if (configured) return configured
  if (env?.DEV) return 'http://127.0.0.1:8000'
  if (typeof window !== 'undefined' && window.location?.origin) return window.location.origin
  return ''
}

export function mcpConnectionSnippet(origin) {
  const base = String(origin || '').replace(/\/$/, '')
  return JSON.stringify(
    {
      mcpServers: {
        insightcase: {
          url: `${base}/mcp`,
          headers: {
            Authorization: 'Bearer YOUR_INTEGRATION_ACCESS_TOKEN',
          },
        },
      },
    },
    null,
    2,
  )
}

export function tokenRequestSnippet(origin) {
  const base = String(origin || '').replace(/\/$/, '')
  return `POST ${base}/api/v1/integrations/oauth/token
{
  "grant_type": "client_credentials",
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}`
}
