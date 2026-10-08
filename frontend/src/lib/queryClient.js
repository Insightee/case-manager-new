import { QueryClient } from '@tanstack/react-query'
import { FOCUS_REFETCH_MIN_AGE_MS, LIVE_FOCUS_REFETCH_MIN_AGE_MS } from './pollingIntervals.js'

/** Unchanged: data older than this refetches on mount / navigation. */
export const QUERY_STALE_TIME_MS = 30_000

/**
 * refetchOnWindowFocus predicate: only refetch when the cached data is at least `minAgeMs` old
 * (react-query still also requires it to be stale). Queries with no data yet keep retrying on focus.
 * @param {number} minAgeMs
 * @param {() => number} [now]
 */
export function refetchOnFocusIfOlderThan(minAgeMs, now = () => Date.now()) {
  return (query) => {
    const updatedAt = query?.state?.dataUpdatedAt || 0
    if (!updatedAt) return true
    return now() - updatedAt >= minAgeMs
  }
}

/** Default: focus refetch only for data older than 10 min (was: any data older than 30 s). */
export const focusRefetchDefault = refetchOnFocusIfOlderThan(FOCUS_REFETCH_MIN_AGE_MS)

/** Live screens (today's schedule, session marking, logs, parent home/appointments): 2 min. */
export const focusRefetchLive = refetchOnFocusIfOlderThan(LIVE_FOCUS_REFETCH_MIN_AGE_MS)

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: QUERY_STALE_TIME_MS,
      refetchOnWindowFocus: focusRefetchDefault,
      refetchOnReconnect: true,
      refetchOnMount: true,
    },
  },
})

export const queryKeys = {
  therapistHome: ['therapist', 'home'],
  therapistWorkspace: ['therapist', 'sessions', 'workspace'],
  therapistDailyLogs: (userId) => ['therapist', 'daily-logs', userId ?? 'self'],
  therapistReportsPipeline: ['therapist', 'reports', 'pipeline'],
  parentHome: ['parent', 'home'],
  parentCases: ['parent', 'cases'],
  parentBootstrap: ['parent', 'bootstrap'],
  parentAppointments: ['parent', 'appointments'],
  adminHome: ['admin', 'home'],
  adminCmHome: ['admin', 'cm', 'home'],
  notifications: (unreadOnly) => ['notifications', { unreadOnly }],
  caseTimeline: (caseId) => ['admin', 'case', caseId, 'timeline'],
  auditEntity: (entityType, entityId) => ['admin', 'audit', entityType, entityId],
  caseDocuments: (caseId) => ['case', caseId, 'documents'],
  caseDocument: (documentId) => ['case', 'document', documentId],
  parentDocuments: ['parent', 'documents'],
}
