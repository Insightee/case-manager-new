/** Therapist portal actions — used for shortcuts and usage-based ordering. */

export const THERAPIST_ACTIONS = [
  {
    id: 'logs',
    to: '/therapist/logs',
    label: 'Submit daily log',
    description: 'Record today’s session and attendance',
    icon: '☰',
    tone: 'primary',
    defaultWeight: 12,
  },
  {
    id: 'cases',
    to: '/therapist/cases',
    label: 'My cases',
    description: 'View assigned children and case details',
    icon: '◉',
    tone: 'indigo',
    defaultWeight: 8,
  },
  {
    id: 'reports',
    to: '/therapist/reports',
    label: 'Monthly reports',
    description: 'Draft and submit monthly case reports',
    icon: '▣',
    tone: 'violet',
    defaultWeight: 6,
  },
  {
    id: 'invoices',
    to: '/therapist/invoices',
    label: 'Invoices',
    description: 'Generate and track your invoices',
    icon: '₹',
    tone: 'amber',
    defaultWeight: 5,
  },
  {
    id: 'tickets',
    to: '/therapist/tickets',
    label: 'Support tickets',
    description: 'Raise HR, finance, or service requests',
    icon: '✉',
    tone: 'sky',
    defaultWeight: 3,
  },
  {
    id: 'leave',
    to: '/therapist/leave?new=1',
    label: 'Request leave',
    description: 'Apply for annual, sick, or casual leave',
    icon: '📅',
    tone: 'rose',
    defaultWeight: 2,
  },
  {
    id: 'slots',
    to: '/therapist/slots',
    label: 'Open slots',
    description: 'Mark when you are available for sessions',
    icon: '🕐',
    tone: 'teal',
    defaultWeight: 2,
  },
  {
    id: 'profile',
    to: '/therapist/profile',
    label: 'My profile',
    description: 'Update location and availability status',
    icon: '👤',
    tone: 'slate',
    defaultWeight: 1,
  },
]

const STORAGE_PREFIX = 'insightcase:therapist-usage:'
export const THERAPIST_USAGE_EVENT = 'therapist-usage-updated'

function storageKey(userId) {
  return `${STORAGE_PREFIX}${userId}`
}

function loadUsage(userId) {
  if (!userId) return {}
  try {
    const raw = localStorage.getItem(storageKey(userId))
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveUsage(userId, usage) {
  if (!userId) return
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(usage))
  } catch {
    // ignore quota errors
  }
}

/** Map a therapist route path to an action id. */
export function actionIdFromPath(pathname) {
  if (!pathname.startsWith('/therapist')) return null
  if (pathname === '/therapist' || pathname === '/therapist/') return null

  const match = THERAPIST_ACTIONS.find(
    (a) => pathname === a.to || pathname.startsWith(`${a.to}/`),
  )
  return match?.id ?? null
}

/** Record a visit or click for personalization (stored per user in localStorage). */
export function recordTherapistAction(userId, pathnameOrId) {
  if (!userId) return

  const id =
    typeof pathnameOrId === 'string' && pathnameOrId.startsWith('/')
      ? actionIdFromPath(pathnameOrId)
      : pathnameOrId

  if (!id) return

  const usage = loadUsage(userId)
  usage[id] = (usage[id] || 0) + 1
  usage._last = Date.now()
  saveUsage(userId, usage)
  window.dispatchEvent(new Event(THERAPIST_USAGE_EVENT))
}

/** Return actions sorted by how often this user uses them (with sensible defaults for new users). */
export function getFrequentTherapistActions(userId, limit = 4) {
  const usage = loadUsage(userId)

  return [...THERAPIST_ACTIONS]
    .map((action) => ({
      ...action,
      useCount: usage[action.id] || 0,
      score: (usage[action.id] || 0) * 3 + (action.defaultWeight || 0),
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
}

export function hasPersonalizedUsage(userId) {
  const usage = loadUsage(userId)
  return Object.keys(usage).some((k) => k !== '_last' && usage[k] > 0)
}
