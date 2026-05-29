import { listPendingDrafts } from './logDraftStore.js'
import { queryClient, queryKeys } from './queryClient.js'

export function therapistDailyLogsKey(userId) {
  return queryKeys.therapistDailyLogs(userId)
}

export function applySessionStartedToWorkspace(workspace, started) {
  if (!workspace || !started?.id) return workspace
  const sid = Number(started.id)
  return {
    ...workspace,
    active_session: started,
    upcoming: (workspace.upcoming || []).filter((s) => s.id !== sid),
  }
}

export function applySessionEndedToWorkspace(workspace, ended) {
  if (!workspace || !ended?.id) return workspace
  const sid = Number(ended.id)
  const needs = workspace.needs_log || []
  const inNeeds = needs.some((s) => s.id === sid)
  return {
    ...workspace,
    active_session: workspace.active_session?.id === sid ? null : workspace.active_session,
    needs_log: inNeeds
      ? needs.map((s) => (s.id === sid ? { ...s, ...ended } : s))
      : [ended, ...needs],
  }
}

export function applyLogSavedToWorkspace(workspace, sessionId) {
  if (!workspace || sessionId == null) return workspace
  const sid = Number(sessionId)
  return {
    ...workspace,
    active_session:
      workspace.active_session?.id === sid ? null : workspace.active_session,
    needs_log: (workspace.needs_log || []).filter((s) => s.id !== sid),
    upcoming: (workspace.upcoming || []).map((s) =>
      s.id === sid ? { ...s, has_daily_log: true } : s,
    ),
  }
}

export function applyLogSavedToDailyLogs(logs, savedLog, { isEdit = false } = {}) {
  const arr = Array.isArray(logs) ? logs : []
  if (!savedLog?.id) return arr
  if (isEdit) {
    return arr.map((l) => (l.id === savedLog.id ? { ...l, ...savedLog } : l))
  }
  if (arr.some((l) => l.id === savedLog.id)) return arr
  return [savedLog, ...arr]
}

/** Case detail sessions tab — mark session logged without refetching the list. */
export function applyLogSavedToSessions(sessions, sessionId) {
  if (sessionId == null) return sessions
  const sid = Number(sessionId)
  return (Array.isArray(sessions) ? sessions : []).map((s) =>
    s.id === sid ? { ...s, has_daily_log: true, status: s.status === 'IN_PROGRESS' ? 'COMPLETED' : s.status } : s,
  )
}

export function applyLogSavedToCaseLogs(logs, savedLog, caseId, { isEdit = false } = {}) {
  const withCase = savedLog ? { ...savedLog, case_id: savedLog.case_id ?? Number(caseId) } : savedLog
  return applyLogSavedToDailyLogs(logs, withCase, { isEdit })
}

export function patchCachesAfterSessionStart(started) {
  queryClient.setQueryData(queryKeys.therapistWorkspace, (old) =>
    applySessionStartedToWorkspace(old, started),
  )
  void queryClient.invalidateQueries({ queryKey: queryKeys.therapistHome })
}

export function patchCachesAfterSessionEnd(ended) {
  queryClient.setQueryData(queryKeys.therapistWorkspace, (old) =>
    applySessionEndedToWorkspace(old, ended),
  )
  void queryClient.invalidateQueries({ queryKey: queryKeys.therapistHome })
}

/** Immediate UI after save; background refetch reconciles with server. */
export function patchCachesAfterLogSave({ userId, sessionId, savedLog, isEdit = false }) {
  const sid = sessionId ?? savedLog?.session_id
  queryClient.setQueryData(queryKeys.therapistWorkspace, (old) =>
    applyLogSavedToWorkspace(old, sid),
  )
  if (userId != null) {
    queryClient.setQueryData(therapistDailyLogsKey(userId), (old) =>
      applyLogSavedToDailyLogs(old, savedLog, { isEdit }),
    )
  }
  void queryClient.invalidateQueries({ queryKey: queryKeys.therapistHome })
  void queryClient.invalidateQueries({ queryKey: queryKeys.therapistWorkspace })
  if (userId != null) {
    void queryClient.invalidateQueries({ queryKey: therapistDailyLogsKey(userId) })
  }
}

export async function refreshTherapistLogDraftIds() {
  const pending = await listPendingDrafts()
  return new Set(pending.map((d) => d.sessionId))
}
